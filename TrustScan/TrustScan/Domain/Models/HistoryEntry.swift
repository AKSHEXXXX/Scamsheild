import Foundation

struct HistoryEntry: Identifiable, Codable, Hashable {
  let id: UUID
  let analysisId: UUID
  let verdict: ThreatVerdict
  let threatScore: Double
  let analyzedAt: Date
  let summary: String
  let thumbnailData: Data?
  let resultSnapshot: AnalysisResult
}
