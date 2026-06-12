import XCTest
@testable import TrustScan

final class DTOsDomainMappingTests: XCTestCase {
  func testScanOutDTOMapping_DangerousVerdict() {
    // Arrange
    let dto = ScanOutDTO(
      scan_id: "test-scan-123",
      kind: "analysis",
      risk_score: 95,
      verdict: "dangerous",
      warning_count: 2,
      extracted_text: "Urgent: Your account is locked",
      findings: [
        FindingOutDTO(type: "urgency", severity: "high", title: "Urgent language", detail: "Found urgency")
      ],
      flagged_urls: [FlaggedUrlDTO(url: "http://fake-site.com", final_url: "http://fake-site.com", reputation: "malicious")]
    )

    // Act
    let domainModel = dto.toDomain()

    // Assert
    XCTAssertEqual(domainModel.verdict, .dangerous)
    XCTAssertEqual(domainModel.threatScore, 0.95)
    XCTAssertFalse(domainModel.indicators.isEmpty)
    XCTAssertTrue(domainModel.indicators.contains { $0.category == .urlThreat })
    XCTAssertTrue(domainModel.indicators.contains { $0.category == .urgencyManipulation })
  }

  func testScanOutDTOMapping_SafeVerdict() {
    // Arrange
    let dto = ScanOutDTO(
      scan_id: "test-scan-safe",
      kind: "analysis",
      risk_score: 10,
      verdict: "safe",
      warning_count: 0,
      extracted_text: "Hi Mom, what's for dinner?",
      findings: [],
      flagged_urls: []
    )

    // Act
    let domainModel = dto.toDomain()

    // Assert
    XCTAssertEqual(domainModel.verdict, .safe)
    XCTAssertEqual(domainModel.threatScore, 0.10)
    XCTAssertTrue(domainModel.indicators.isEmpty)
  }
}
