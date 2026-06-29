import Foundation
import UIKit

struct SubmitAnalysisUseCase {
  private let analysisRepository: any AnalysisRepositoryPort
  private let ocrService: OCRService

  init(analysisRepository: any AnalysisRepositoryPort, ocrService: OCRService = OCRService()) {
    self.analysisRepository = analysisRepository
    self.ocrService = ocrService
  }

  func callAsFunction(image: UIImage, fileName: String = "scan-\(UUID().uuidString).jpg") async throws -> (AnalysisResult, String) {
    if let qrPayload = await ocrService.extractQRCode(from: image) {
        let result = try await analysisRepository.analyze(qrPayload: qrPayload)
        return (result, "QR Code Scan")
    }

    let ocrResult = await ocrService.extractText(from: image)

    switch ocrResult {
    case .success(let text, let confidence, _):
      let result = try await analysisRepository.analyze(text: text)
      let sourceString = "On-device (confidence: \(Int(confidence * 100))%)"
      return (result, sourceString)
      
    case .fallbackRequired(let reason):
      let resized = image.resized(toMaxDimension: 1024)
      guard let data = resized.jpegData(compressionQuality: 0.75) else {
        throw AppError.invalidImage
      }
      
      let payload = PreparedImagePayload(
        data: data,
        mimeType: "image/jpeg",
        fileName: fileName
      )
      
      let result = try await analysisRepository.analyze(image: payload, fallbackReason: reason)
      return (result, "Enhanced scan (server)")
    }
  }

  func analyzeQR(payload: String) async throws -> (AnalysisResult, String) {
    let result = try await analysisRepository.analyze(qrPayload: payload)
    return (result, "QR Code Scan")
  }

  func analyzeText(_ text: String) async throws -> (AnalysisResult, String) {
    let result = try await analysisRepository.analyze(text: text)
    return (result, "Text Scan")
  }
}

// MARK: - Feedback Use Case

struct SubmitFeedbackUseCase {
  private let repository: any AnalysisRepositoryPort

  init(repository: any AnalysisRepositoryPort) {
    self.repository = repository
  }

  func execute(scanId: String, label: String) async throws {
    try await repository.submitFeedback(scanId: scanId, label: label)
  }
}
import Vision
import UIKit

actor OCRService {

    enum OCRResult {
        case success(text: String, confidence: Float, source: OCRSource)
        case fallbackRequired(reason: String)
    }

    enum OCRSource {
        case onDevice
    }

    private let confidenceThreshold: Float = 0.6
    private let minimumTextLength = 20
    
    func extractQRCode(from image: UIImage) async -> String? {
        guard let cgImage = image.cgImage else { return nil }
        
        let request = VNDetectBarcodesRequest()
        let orientation = CGImagePropertyOrientation(image.imageOrientation)
        let handler = VNImageRequestHandler(cgImage: cgImage, orientation: orientation, options: [:])
        
        do {
            try handler.perform([request])
            if let observations = request.results,
               let barcode = observations.first,
               let payload = barcode.payloadStringValue {
                return payload
            }
        } catch {
            print("QR detection error: \(error)")
        }
        
        return nil
    }

    func extractText(from image: UIImage) async -> OCRResult {
        guard let cgImage = image.cgImage else {
            return .fallbackRequired(reason: "Invalid image format")
        }

        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["en-IN", "hi-IN", "en-US"]
        request.usesLanguageCorrection = true
        request.minimumTextHeight = 0.01

        let orientation = CGImagePropertyOrientation(image.imageOrientation)
        let handler = VNImageRequestHandler(cgImage: cgImage, orientation: orientation, options: [:])
        
        do {
            try handler.perform([request])
            
            guard let observations = request.results,
                  !observations.isEmpty else {
                return .fallbackRequired(reason: "Vision request failed or no text")
            }

            let candidates = observations.compactMap { $0.topCandidates(1).first }
            let avgConfidence = candidates.map(\.confidence).reduce(0, +) / Float(max(candidates.count, 1))
            let fullText = candidates.map(\.string).joined(separator: "\n")

            if fullText.trimmingCharacters(in: .whitespacesAndNewlines).count < self.minimumTextLength {
                return .fallbackRequired(reason: "Insufficient text extracted")
            }

            if avgConfidence < self.confidenceThreshold {
                return .fallbackRequired(reason: "Low confidence: \(avgConfidence)")
            }

            return .success(
                text: fullText,
                confidence: avgConfidence,
                source: .onDevice
            )
            
        } catch {
            return .fallbackRequired(reason: "Vision handler threw error: \(error.localizedDescription)")
        }
    }
}

private extension UIImage {
  func resized(toMaxDimension max: CGFloat) -> UIImage {
    let longest = Swift.max(size.width, size.height)
    guard longest > max else { return self }
    let scale = max / longest
    let newSize = CGSize(width: (size.width * scale).rounded(), height: (size.height * scale).rounded())
    let renderer = UIGraphicsImageRenderer(size: newSize)
    return renderer.image { _ in draw(in: CGRect(origin: .zero, size: newSize)) }
  }
}

extension CGImagePropertyOrientation {
    init(_ orientation: UIImage.Orientation) {
        switch orientation {
        case .up: self = .up
        case .upMirrored: self = .upMirrored
        case .down: self = .down
        case .downMirrored: self = .downMirrored
        case .left: self = .left
        case .leftMirrored: self = .leftMirrored
        case .right: self = .right
        case .rightMirrored: self = .rightMirrored
        @unknown default: self = .up
        }
    }
}
