import XCTest
@testable import TrustScan

@MainActor
final class HistoryViewModelTests: XCTestCase {
  func testLoadHistory_Success() async {
    // Arrange
    let mockRepo = MockHistoryRepository()
    let entry = HistoryEntry(id: UUID(), analysisId: UUID(), verdict: .suspicious, threatScore: 0.5, analyzedAt: Date(), summary: "Test", thumbnailData: nil, resultSnapshot: AnalysisResult(id: UUID(), verdict: .suspicious, threatScore: 0.5, summary: "", extractedText: "", indicators: [], recommendations: [], analysisTimestamp: Date(), educationalContext: nil))
    mockRepo.mockEntries = [entry]

    let viewModel = HistoryViewModel(
      loadHistoryUseCase: LoadHistoryUseCase(historyRepository: mockRepo),
      deleteHistoryEntryUseCase: DeleteHistoryEntryUseCase(historyRepository: mockRepo)
    )

    // Act
    await viewModel.loadHistory()

    // Assert
    if case let .success(loadedEntries) = viewModel.state {
      XCTAssertEqual(loadedEntries.count, 1)
      XCTAssertEqual(loadedEntries.first?.id, entry.id)
    } else {
      XCTFail("State should be success")
    }
  }

  func testLoadHistory_Empty() async {
    // Arrange
    let mockRepo = MockHistoryRepository()
    mockRepo.mockEntries = []

    let viewModel = HistoryViewModel(
      loadHistoryUseCase: LoadHistoryUseCase(historyRepository: mockRepo),
      deleteHistoryEntryUseCase: DeleteHistoryEntryUseCase(historyRepository: mockRepo)
    )

    // Act
    await viewModel.loadHistory()

    // Assert
    if case .empty = viewModel.state {
      // Success
    } else {
      XCTFail("State should be empty")
    }
  }
}

actor MockHistoryRepository: HistoryRepositoryPort {
  var mockEntries: [HistoryEntry] = []
  var saveWasCalled = false
  var deleteWasCalled = false
  var deleteAllWasCalled = false

  func loadHistory() async throws -> [HistoryEntry] {
    return mockEntries
  }

  func save(result: AnalysisResult, thumbnailData: Data?) async throws {
    saveWasCalled = true
  }

  func delete(entryID: UUID) async throws {
    deleteWasCalled = true
    mockEntries.removeAll { $0.id == entryID }
  }

  func deleteAll() async throws {
    deleteAllWasCalled = true
    mockEntries.removeAll()
  }
}
