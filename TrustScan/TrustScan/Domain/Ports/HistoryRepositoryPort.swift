import Foundation

protocol HistoryRepositoryPort {
  func loadHistory() async throws -> [HistoryEntry]
  func save(result: AnalysisResult, thumbnailData: Data?) async throws
  func delete(entryID: UUID) async throws
  func deleteAll() async throws
}
