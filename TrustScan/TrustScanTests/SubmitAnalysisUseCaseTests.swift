import XCTest
@testable import TrustScan

final class SubmitAnalysisUseCaseTests: XCTestCase {
  func testSubmitAnalysis_SuccessfulScan_ReturnsMappedResult() async throws {
    // Arrange
    let repository = MockAnalysisRepository()
    let expectedResult = AnalysisResult(
      id: UUID(),
      verdict: .dangerous,
      threatScore: 0.95,
      summary: "High risk test",
      extractedText: "test data",
      indicators: [],
      recommendations: [],
      analysisTimestamp: Date(),
      educationalContext: nil
    )
    repository.mockResult = expectedResult
    let useCase = SubmitAnalysisUseCase(analysisRepository: repository)

    // Act
    let payload = PreparedImagePayload(data: Data(), mimeType: "image/jpeg", fileName: "test.jpg")
    let result = try await useCase.callAsFunction(image: payload)

    // Assert
    XCTAssertEqual(result.verdict, .dangerous)
    XCTAssertEqual(result.threatScore, 0.95)
    XCTAssertTrue(repository.analyzeWasCalled)
  }

  func testSubmitAnalysis_RepositoryThrowsError_PropagatesError() async {
    // Arrange
    let repository = MockAnalysisRepository()
    repository.mockError = AppError.networkUnavailable
    let useCase = SubmitAnalysisUseCase(analysisRepository: repository)

    // Act & Assert
    do {
      let payload = PreparedImagePayload(data: Data(), mimeType: "image/jpeg", fileName: "test.jpg")
      _ = try await useCase.callAsFunction(image: payload)
      XCTFail("Expected an error to be thrown")
    } catch {
      XCTAssertEqual(error as? AppError, AppError.networkUnavailable)
    }
  }
}

class MockAnalysisRepository: AnalysisRepositoryPort {
  var mockResult: AnalysisResult?
  var mockError: Error?
  private(set) var analyzeWasCalled = false

  func analyze(image: PreparedImagePayload) async throws -> AnalysisResult {
    analyzeWasCalled = true
    if let error = mockError {
      throw error
    }
    guard let result = mockResult else {
      fatalError("Mock result not set")
    }
    return result
  }
}
