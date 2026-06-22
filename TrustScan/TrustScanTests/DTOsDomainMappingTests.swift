import XCTest
@testable import TrustScan

final class DTOsDomainMappingTests: XCTestCase {
  func testScanOutDTOMapping_ScamVerdict() throws {
    // Arrange — uses new contract fields (scam_score, high_risk verdict, message in findings)
    let json = """
    {
        "scan_id": "test-scan-123",
        "scam_score": 95,
        "verdict": "high_risk",
        "flagged": true,
        "warning_count": 3,
        "top_signal": "urgency_language",
        "findings": [
            {"type": "urgency", "severity": "high", "message": "Found urgency language"}
        ],
        "flagged_urls": ["http://fake-site.com"]
    }
    """.data(using: .utf8)!

    let dto = try JSONDecoder().decode(ScanOutDTO.self, from: json)

    // Act
    let domainModel = dto.toDomain()

    // Assert
    XCTAssertEqual(domainModel.verdict, .scam)           // high_risk → .scam
    XCTAssertEqual(domainModel.score, 95)
    XCTAssertEqual(domainModel.warningCount, 3)
    XCTAssertEqual(domainModel.topSignal, "urgency_language")
    XCTAssertFalse(domainModel.findings.isEmpty)
    XCTAssertEqual(domainModel.findings.first?.description, "Found urgency language")
    XCTAssertTrue(domainModel.flaggedUrls.contains("http://fake-site.com"))
  }

  func testScanOutDTOMapping_SafeVerdict() throws {
    // Arrange — uses new contract fields (scam_score, low_risk verdict)
    let json = """
    {
        "scan_id": "test-scan-safe",
        "scam_score": 10,
        "verdict": "low_risk",
        "flagged": false,
        "warning_count": 0,
        "findings": [],
        "flagged_urls": []
    }
    """.data(using: .utf8)!

    let dto = try JSONDecoder().decode(ScanOutDTO.self, from: json)

    // Act
    let domainModel = dto.toDomain()

    // Assert
    XCTAssertEqual(domainModel.verdict, .safe)           // low_risk → .safe
    XCTAssertEqual(domainModel.score, 10)
    XCTAssertEqual(domainModel.warningCount, 0)
    XCTAssertTrue(domainModel.findings.isEmpty)
    XCTAssertTrue(domainModel.flaggedUrls.isEmpty)
  }
}
