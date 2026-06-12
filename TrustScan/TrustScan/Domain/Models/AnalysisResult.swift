import Foundation

enum ThreatVerdict: String, Codable, CaseIterable, Hashable, Identifiable {
  case safe
  case suspicious
  case dangerous
  case inconclusive

  var id: String { rawValue }
}

enum ThreatCategory: String, Codable, Hashable {
  case urlThreat
  case impersonation
  case urgencyManipulation
  case personalDataRequest
  case paymentFraud
  case unknownSender
  case maliciousContent
  case socialEngineering
  case other
}

enum IndicatorSeverity: String, Codable, Hashable {
  case low
  case medium
  case high
}

enum ActionType: String, Codable, Hashable {
  case informational
  case deepLink
  case systemAction
}

struct AnalysisResult: Identifiable, Codable, Hashable {
  let id: UUID
  let verdict: ThreatVerdict
  let threatScore: Double
  let summary: String
  let extractedText: String
  let indicators: [ThreatIndicator]
  let recommendations: [RecommendedAction]
  let analysisTimestamp: Date
  let educationalContext: EducationalContent?
}
