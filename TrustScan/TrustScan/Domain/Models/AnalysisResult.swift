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
  let meta: ScanMeta?
  let analysisTimestamp: Date
}
