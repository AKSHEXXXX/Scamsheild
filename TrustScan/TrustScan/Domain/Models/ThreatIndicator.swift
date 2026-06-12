import Foundation

struct ThreatIndicator: Identifiable, Codable, Hashable {
  let id: UUID
  let category: ThreatCategory
  let title: String
  let description: String
  let severity: IndicatorSeverity
  let rawValue: String?
}

struct RecommendedAction: Identifiable, Codable, Hashable {
  let id: UUID
  let priority: Int
  let actionText: String
  let actionType: ActionType
}

struct EducationalContent: Codable, Hashable {
  let title: String
  let body: String
}
