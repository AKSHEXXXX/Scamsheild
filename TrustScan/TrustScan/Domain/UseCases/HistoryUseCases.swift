import Foundation

struct LoadHistoryUseCase {
  private let historyRepository: any HistoryRepositoryPort

  init(historyRepository: any HistoryRepositoryPort) {
    self.historyRepository = historyRepository
  }

  func callAsFunction() async throws -> [HistoryEntry] {
    try await historyRepository.loadHistory()
  }
}

struct SaveHistoryEntryUseCase {
  private let historyRepository: any HistoryRepositoryPort

  init(historyRepository: any HistoryRepositoryPort) {
    self.historyRepository = historyRepository
  }

  func callAsFunction(result: AnalysisResult, thumbnailData: Data?) async throws {
    try await historyRepository.save(result: result, thumbnailData: thumbnailData)
  }
}

struct DeleteHistoryEntryUseCase {
  private let historyRepository: any HistoryRepositoryPort

  init(historyRepository: any HistoryRepositoryPort) {
    self.historyRepository = historyRepository
  }

  func callAsFunction(entryID: UUID) async throws {
    try await historyRepository.delete(entryID: entryID)
  }
}

struct ClearHistoryUseCase {
  private let historyRepository: any HistoryRepositoryPort

  init(historyRepository: any HistoryRepositoryPort) {
    self.historyRepository = historyRepository
  }

  func callAsFunction() async throws {
    try await historyRepository.deleteAll()
  }
}
