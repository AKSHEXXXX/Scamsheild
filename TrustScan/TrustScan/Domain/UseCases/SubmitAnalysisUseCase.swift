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
      guard let data = image.jpegData(compressionQuality: 0.8) else {
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
import Vision
import UIKit

actor OCRService {

    enum OCRResult {
        case success(text: String, confidence: Float, source: OCRSource)
        case fallbackRequired(reason: String)
    }

    enum OCRSource {
        case onDevice
        case backend
    }

    private let confidenceThreshold: Float = 0.6
    private let minimumTextLength = 20
    
    func extractQRCode(from image: UIImage) async -> String? {
        guard let cgImage = image.cgImage else { return nil }
        
        return await withCheckedContinuation { continuation in
            let request = VNDetectBarcodesRequest { request, error in
                guard error == nil,
                      let observations = request.results as? [VNBarcodeObservation],
                      let barcode = observations.first,
                      let payload = barcode.payloadStringValue else {
                    continuation.resume(returning: nil)
                    return
                }
                continuation.resume(returning: payload)
            }
            
            let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
            do {
                try handler.perform([request])
            } catch {
                continuation.resume(returning: nil)
            }
        }
    }

    func extractText(from image: UIImage) async -> OCRResult {
        guard let cgImage = image.cgImage else {
            return .fallbackRequired(reason: "Invalid image format")
        }

        return await withCheckedContinuation { continuation in
            let request = VNRecognizeTextRequest { request, error in
                guard error == nil,
                      let observations = request.results as? [VNRecognizedTextObservation],
                      !observations.isEmpty else {
                    continuation.resume(returning: .fallbackRequired(reason: "Vision request failed"))
                    return
                }

                let candidates = observations.compactMap { $0.topCandidates(1).first }
                let avgConfidence = candidates.map(\.confidence).reduce(0, +) / Float(max(candidates.count, 1))
                let fullText = candidates.map(\.string).joined(separator: "\n")

                if fullText.trimmingCharacters(in: .whitespacesAndNewlines).count < self.minimumTextLength {
                    continuation.resume(returning: .fallbackRequired(reason: "Insufficient text extracted"))
                    return
                }

                if avgConfidence < self.confidenceThreshold {
                    continuation.resume(returning: .fallbackRequired(reason: "Low confidence: \(avgConfidence)"))
                    return
                }

                continuation.resume(returning: .success(
                    text: fullText,
                    confidence: avgConfidence,
                    source: .onDevice
                ))
            }

            request.recognitionLevel = .accurate
            request.recognitionLanguages = ["en-IN", "hi-IN", "en-US"]
            request.usesLanguageCorrection = true
            request.minimumTextHeight = 0.01

            let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
            do {
                try handler.perform([request])
            } catch {
                continuation.resume(returning: .fallbackRequired(reason: "Vision handler threw error"))
            }
        }
    }
}
