import Foundation

enum ThreatVerdict: String, Codable, CaseIterable, Hashable, Identifiable {
  case safe
  case suspicious
  case scam

  var id: String { rawValue }
}

struct Finding: Codable, Hashable {
  let type: String
  let value: String
  let severity: String
  let description: String
}

struct ScanMeta: Codable, Hashable {
  let ocrMethod: String?
  let ocrConfidence: Double?
  let ocrFallback: Bool?
}

struct AnalysisResult: Identifiable, Codable, Hashable {
  let id: UUID
  let verdict: ThreatVerdict
  let score: Int
  let flagged: Bool
  let summary: String
  let extractedText: String
  let findings: [Finding]
  let flaggedUrls: [String]
  let topSignal: String?
  let warningCount: Int
  let meta: ScanMeta?
  let analysisTimestamp: Date

  var contextualSummary: String {
    switch verdict {
    case .safe:
      if flaggedUrls.isEmpty && findings.isEmpty {
        return "No scam patterns found. This content scored \(score)% — well within safe limits. You can engage with it normally."
      } else if !flaggedUrls.isEmpty {
        let n = flaggedUrls.count
        return "This content scored \(score)% — low risk overall. However, \(n) shortened or suspicious link\(n == 1 ? "" : "s") \(n == 1 ? "was" : "were") detected, which \(n == 1 ? "is" : "are") commonly used to hide malicious destinations. Do not click unless you fully trust the source."
      } else {
        let n = findings.count
        return "Risk level is low at \(score)%. \(n) minor indicator\(n == 1 ? "" : "s") \(n == 1 ? "was" : "were") flagged — likely not dangerous, but review the details below before proceeding."
      }
    case .suspicious:
      if let signal = topSignal {
        let name = signal.replacingOccurrences(of: "_", with: " ").capitalized
        return "\(name) was detected in this content, pushing the risk score to \(score)%. This is a common tactic used in phishing and fraud messages. Do not share personal information or click any links until you have verified the source independently."
      }
      return "Several suspicious patterns were detected (risk score: \(score)%). This content shows characteristics commonly found in scam messages. Proceed with caution — verify the sender independently before taking any action."
    case .scam:
      if let signal = topSignal {
        let name = signal.replacingOccurrences(of: "_", with: " ").capitalized
        return "High-confidence scam detected — \(name) found with a risk score of \(score)%. This is a known fraud pattern. Do not respond, click any links, or share personal or financial information. Block and report the sender."
      }
      return "High-risk content detected (score: \(score)%). Multiple scam indicators are present in this message. Do not engage — block and report the sender immediately."
    }
  }
}
