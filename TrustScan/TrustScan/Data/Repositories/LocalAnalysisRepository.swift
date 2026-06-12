import Foundation
import UIKit
import Vision

struct LocalAnalysisRepository: AnalysisRepositoryPort {
  func analyze(image: PreparedImagePayload) async throws -> AnalysisResult {
    guard let uiImage = UIImage(data: image.data) else {
      throw AppError.invalidImage
    }

    guard let cgImage = uiImage.cgImage ?? renderedCGImage(from: uiImage) else {
      throw AppError.invalidImage
    }

    let extractedText = try recognizeText(in: cgImage).trimmingCharacters(in: .whitespacesAndNewlines)
    return buildResult(from: extractedText)
  }

  private func renderedCGImage(from image: UIImage) -> CGImage? {
    let format = UIGraphicsImageRendererFormat.default()
    format.scale = 1
    let renderer = UIGraphicsImageRenderer(size: image.size, format: format)
    let renderedImage = renderer.image { _ in
      image.draw(in: CGRect(origin: .zero, size: image.size))
    }
    return renderedImage.cgImage
  }

  private func recognizeText(in cgImage: CGImage) throws -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["en-US"]

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try handler.perform([request])

    let observations = request.results ?? []
    let lines = observations.compactMap { observation in
      observation.topCandidates(1).first?.string
    }

    return lines.joined(separator: "\n")
  }

  private func buildResult(from text: String) -> AnalysisResult {
    let normalized = text.lowercased()

    let urgentHits = matches(in: normalized, phrases: ["urgent", "act now", "immediately", "suspended", "expired", "limited time", "final notice"])
    let impersonationHits = matches(in: normalized, phrases: ["bank", "paypal", "apple", "microsoft", "amazon", "delivery", "irs", "government", "fedex"])
    let credentialHits = matches(in: normalized, phrases: ["password", "otp", "verification code", "login", "confirm identity", "social security", "ssn"])
    let paymentHits = matches(in: normalized, phrases: ["gift card", "wire transfer", "bitcoin", "crypto", "invoice", "payment", "fee due"])
    let urls = detectedLinks(in: text)

    var score = 0.0
    var indicators: [ThreatIndicator] = []

    if !urls.isEmpty {
      score += 0.18
      indicators.append(ThreatIndicator(id: UUID(), category: .urlThreat, title: "External link detected", description: "Scam messages often push you to act through a link before you stop to verify it.", severity: .medium, rawValue: urls.joined(separator: ", ")))
    }

    if !urgentHits.isEmpty {
      score += 0.22
      indicators.append(ThreatIndicator(id: UUID(), category: .urgencyManipulation, title: "Urgency language", description: "The message uses pressure words that try to rush a decision.", severity: urgentHits.count > 1 ? .high : .medium, rawValue: urgentHits.joined(separator: ", ")))
    }

    if !impersonationHits.isEmpty {
      score += 0.18
      indicators.append(ThreatIndicator(id: UUID(), category: .impersonation, title: "Brand or authority impersonation", description: "The content references a trusted company or authority.", severity: .medium, rawValue: impersonationHits.joined(separator: ", ")))
    }

    if !credentialHits.isEmpty {
      score += 0.26
      indicators.append(ThreatIndicator(id: UUID(), category: .personalDataRequest, title: "Sensitive information request", description: "The message appears to ask for credentials, codes, or identity details.", severity: .high, rawValue: credentialHits.joined(separator: ", ")))
    }

    if !paymentHits.isEmpty {
      score += 0.24
      indicators.append(ThreatIndicator(id: UUID(), category: .paymentFraud, title: "Payment pressure", description: "Requests involving urgent payment, gift cards, or crypto are strong scam signals.", severity: .high, rawValue: paymentHits.joined(separator: ", ")))
    }

    score = min(score, 0.99)

    let verdict: ThreatVerdict
    if text.isEmpty {
      verdict = .inconclusive
    } else if score >= 0.72 {
      verdict = .dangerous
    } else if score >= 0.38 {
      verdict = .suspicious
    } else if indicators.isEmpty {
      verdict = .safe
      score = 0.14
    } else {
      verdict = .suspicious
    }

    let summary: String
    switch verdict {
    case .dangerous: summary = "This screenshot shows several high-risk scam traits."
    case .suspicious: summary = "This screenshot contains warning signs that deserve caution."
    case .safe: summary = "No clear scam traits stood out, but verify the sender before acting."
    case .inconclusive: summary = "The scan was only partially readable and needs a manual check."
    }

    var recommendations = [RecommendedAction]()
    if verdict == .dangerous || verdict == .suspicious {
      recommendations.append(RecommendedAction(id: UUID(), priority: 1, actionText: "Do not tap links or reply until the sender is verified.", actionType: .informational))
    }
    if recommendations.isEmpty {
      recommendations.append(RecommendedAction(id: UUID(), priority: 1, actionText: "If unsure, verify the sender independently before responding.", actionType: .informational))
    }

    let education: EducationalContent
    switch verdict {
    case .dangerous: education = EducationalContent(title: "Why this matters", body: "Scam campaigns combine urgency, authority, and a shortcut to action.")
    case .suspicious: education = EducationalContent(title: "What to watch for", body: "Messages that push you outside your normal routine deserve extra scrutiny.")
    case .safe: education = EducationalContent(title: "Healthy habit", body: "Independent verification is still the safest response for anything important.")
    case .inconclusive: education = EducationalContent(title: "Better scan quality helps", body: "Clear screenshots with full message and sender details give better evidence.")
    }

    return AnalysisResult(
      id: UUID(), verdict: verdict, threatScore: score, summary: summary,
      extractedText: text, indicators: indicators, recommendations: recommendations,
      analysisTimestamp: Date(), educationalContext: education
    )
  }

  private func matches(in text: String, phrases: [String]) -> [String] {
    phrases.filter { text.contains($0) }
  }

  private func detectedLinks(in text: String) -> [String] {
    guard let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue) else { return [] }
    let range = NSRange(location: 0, length: (text as NSString).length)
    return detector.matches(in: text, options: [], range: range).compactMap { $0.url?.absoluteString }
  }
}
