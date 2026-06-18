import XCTest
@testable import TrustScan

final class SubmitAnalysisUseCaseTests: XCTestCase {
  func testSubmitAnalysis_WhenOCRServiceSucceeds_CallsAnalyzeText() async throws {
    // Arrange
    let repository = MockAnalysisRepository()
    let expectedResult = AnalysisResult(
      id: UUID(),
      verdict: .scam,
      score: 95,
      flagged: true,
      summary: "High risk test",
      extractedText: "test data",
      findings: [],
      flaggedUrls: [],
      meta: nil,
      analysisTimestamp: Date()
    )
    repository.mockResult = expectedResult
    
    // Create an image containing text to force OCR success
    let testImage = createTestImage(withText: "This is a very clear and readable text that exceeds the twenty characters length limit for testing purposes")
    let useCase = SubmitAnalysisUseCase(analysisRepository: repository)

    // Act
    let (result, source) = try await useCase.callAsFunction(image: testImage)

    // Assert
    XCTAssertEqual(result.verdict, .scam)
    XCTAssertTrue(repository.analyzeTextWasCalled)
    XCTAssertFalse(repository.analyzeImageWasCalled)
    XCTAssertTrue(source.contains("On-device"))
  }

  func testSubmitAnalysis_WhenOCRServiceFails_CallsAnalyzeImage() async throws {
    // Arrange
    let repository = MockAnalysisRepository()
    let expectedResult = AnalysisResult(
      id: UUID(),
      verdict: .safe,
      score: 10,
      flagged: false,
      summary: "Safe test",
      extractedText: "",
      findings: [],
      flaggedUrls: [],
      meta: nil,
      analysisTimestamp: Date()
    )
    repository.mockResult = expectedResult
    
    // Create an empty image to force OCR fallback
    let testImage = UIImage() 
    let useCase = SubmitAnalysisUseCase(analysisRepository: repository)

    // Act
    do {
      let (result, source) = try await useCase.callAsFunction(image: testImage)
      
      // Assert
      XCTAssertEqual(result.verdict, .safe)
      XCTAssertFalse(repository.analyzeTextWasCalled)
      XCTAssertTrue(repository.analyzeImageWasCalled)
      XCTAssertEqual(source, "Enhanced scan (server)")
    } catch {
      XCTAssertEqual(error as? AppError, AppError.invalidImage)
    }
  }

  // Helper to create an image with text
  private func createTestImage(withText text: String) -> UIImage {
    let size = CGSize(width: 800, height: 200)
    UIGraphicsBeginImageContextWithOptions(size, false, 0.0)
    let context = UIGraphicsGetCurrentContext()
    
    // White background
    context?.setFillColor(UIColor.white.cgColor)
    context?.fill(CGRect(origin: .zero, size: size))
    
    // Draw text
    let attributes: [NSAttributedString.Key: Any] = [
        .font: UIFont.systemFont(ofSize: 24),
        .foregroundColor: UIColor.black
    ]
    text.draw(in: CGRect(x: 10, y: 10, width: 780, height: 180), withAttributes: attributes)
    
    let image = UIGraphicsGetImageFromCurrentImageContext()
    UIGraphicsEndImageContext()
    return image ?? UIImage()
  }
}

class MockAnalysisRepository: AnalysisRepositoryPort {
  var mockResult: AnalysisResult?
  var mockError: Error?
  private(set) var analyzeTextWasCalled = false
  private(set) var analyzeImageWasCalled = false

  func analyze(text: String) async throws -> AnalysisResult {
    analyzeTextWasCalled = true
    if let error = mockError { throw error }
    return mockResult!
  }

  func analyze(image: PreparedImagePayload, fallbackReason: String) async throws -> AnalysisResult {
    analyzeImageWasCalled = true
    if let error = mockError { throw error }
    return mockResult!
  }

  func analyze(qrPayload: String) async throws -> AnalysisResult {
    if let error = mockError { throw error }
    return mockResult!
  }
}

final class OCRServiceTests: XCTestCase {
  
  func testExtractText_WithInvalidImage_ReturnsFallback() async {
    let service = OCRService()
    let invalidImage = UIImage()
    
    let result = await service.extractText(from: invalidImage)
    
    if case .fallbackRequired(let reason) = result {
      XCTAssertEqual(reason, "Invalid image format")
    } else {
      XCTFail("Expected fallbackRequired due to invalid image")
    }
  }

  func testExtractText_WithClearText_ReturnsSuccess() async {
    let service = OCRService()
    
    let text = "This is a sufficiently long string of text designed to easily pass the twenty character minimum length requirement for the OCR fallback threshold."
    let size = CGSize(width: 800, height: 200)
    UIGraphicsBeginImageContextWithOptions(size, false, 2.0)
    let context = UIGraphicsGetCurrentContext()
    context?.setFillColor(UIColor.white.cgColor)
    context?.fill(CGRect(origin: .zero, size: size))
    let attributes: [NSAttributedString.Key: Any] = [
        .font: UIFont.systemFont(ofSize: 24),
        .foregroundColor: UIColor.black
    ]
    text.draw(in: CGRect(x: 10, y: 10, width: 780, height: 180), withAttributes: attributes)
    let validImage = UIGraphicsGetImageFromCurrentImageContext() ?? UIImage()
    UIGraphicsEndImageContext()

    let result = await service.extractText(from: validImage)
    
    if case .success(let extractedText, let confidence, let source) = result {
      XCTAssertTrue(extractedText.contains("sufficiently"))
      XCTAssertGreaterThan(confidence, 0.6)
      XCTAssertEqual(source, .onDevice)
    } else {
      XCTFail("Expected success, but got \(result)")
    }
  }
}
