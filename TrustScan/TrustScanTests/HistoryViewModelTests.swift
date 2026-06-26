import XCTest
@testable import TrustScan

@MainActor
final class HistoryViewModelTests: XCTestCase {
  func testLoadHistory_Success() async {
    // Arrange
    let mockRepo = MockHistoryRepository()
    let entry = HistoryEntry(
      id: UUID(),
      analysisId: UUID(),
      verdict: .suspicious,
      score: 50,
      analyzedAt: Date(),
      summary: "Test",
      thumbnailData: nil,
      resultSnapshot: AnalysisResult(
        id: UUID(),
        verdict: .suspicious,
        score: 50,
        flagged: true,
        summary: "",
        extractedText: "",
        findings: [],
        flaggedUrls: [],
        topSignal: nil,
        warningCount: 0,
        meta: nil,
        analysisTimestamp: Date()
      )
    )
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

  func testLoadHistory_WithLimit_ReturnsPrefix() async {
    // Arrange
    let mockRepo = MockHistoryRepository()
    let first = makeEntry(summary: "First")
    let second = makeEntry(summary: "Second")
    mockRepo.mockEntries = [first, second]

    let viewModel = HistoryViewModel(
      loadHistoryUseCase: LoadHistoryUseCase(historyRepository: mockRepo),
      deleteHistoryEntryUseCase: DeleteHistoryEntryUseCase(historyRepository: mockRepo)
    )

    // Act
    await viewModel.loadHistory(limit: 1)

    // Assert
    if case let .success(loadedEntries) = viewModel.state {
      let receivedLimit = await mockRepo.lastReceivedLimit
      XCTAssertEqual(loadedEntries.map(\.id), [first.id])
      XCTAssertEqual(receivedLimit, 1)
    } else {
      XCTFail("State should be success")
    }
  }

  private func makeEntry(summary: String) -> HistoryEntry {
    HistoryEntry(
      id: UUID(),
      analysisId: UUID(),
      verdict: .suspicious,
      score: 50,
      analyzedAt: Date(),
      summary: summary,
      thumbnailData: nil,
      resultSnapshot: AnalysisResult(
        id: UUID(),
        verdict: .suspicious,
        score: 50,
        flagged: true,
        summary: summary,
        extractedText: "",
        findings: [],
        flaggedUrls: [],
        topSignal: nil,
        warningCount: 0,
        meta: nil,
        analysisTimestamp: Date()
      )
    )
  }
}

actor MockHistoryRepository: HistoryRepositoryPort {
  var mockEntries: [HistoryEntry] = []
  var saveWasCalled = false
  var deleteWasCalled = false
  var deleteAllWasCalled = false
  var lastReceivedLimit: Int?

  func loadHistory(limit: Int?) async throws -> [HistoryEntry] {
    lastReceivedLimit = limit
    if let limit {
      return Array(mockEntries.prefix(max(limit, 0)))
    }
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
