import XCTest
@testable import TrustScan

final class DTOsDomainMappingTests: XCTestCase {
  func testScanOutDTOMapping_ScamVerdict() throws {
    // Arrange
    let json = """
    {
        "scan_id": "test-scan-123",
        "risk_score": 95,
        "verdict": "scam",
        "flagged": true,
        "findings": [
            {"type": "urgency", "severity": "high", "description": "Found urgency language"}
        ],
        "flagged_urls": ["http://fake-site.com"]
    }
    """.data(using: .utf8)!

    let dto = try JSONDecoder().decode(ScanOutDTO.self, from: json)

    // Act
    let domainModel = dto.toDomain()

    // Assert
    XCTAssertEqual(domainModel.verdict, .scam)
    XCTAssertEqual(domainModel.score, 95)
    XCTAssertFalse(domainModel.findings.isEmpty)
    XCTAssertTrue(domainModel.flaggedUrls.contains("http://fake-site.com"))
  }

  func testScanOutDTOMapping_SafeVerdict() throws {
    // Arrange
    let json = """
    {
        "scan_id": "test-scan-safe",
        "risk_score": 10,
        "verdict": "safe",
        "flagged": false,
        "findings": [],
        "flagged_urls": []
    }
    """.data(using: .utf8)!

    let dto = try JSONDecoder().decode(ScanOutDTO.self, from: json)

    // Act
    let domainModel = dto.toDomain()

    // Assert
    XCTAssertEqual(domainModel.verdict, .safe)
    XCTAssertEqual(domainModel.score, 10)
    XCTAssertTrue(domainModel.findings.isEmpty)
    XCTAssertTrue(domainModel.flaggedUrls.isEmpty)
  }
}
