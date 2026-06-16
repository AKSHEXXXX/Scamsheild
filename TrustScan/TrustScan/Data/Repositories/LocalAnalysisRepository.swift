import Foundation
import UIKit

struct LocalAnalysisRepository: AnalysisRepositoryPort {
  func analyze(text: String) async throws -> AnalysisResult {
    try await Task.sleep(nanoseconds: 1_000_000_000)
    return buildMockResult(from: text)
  }

  func analyze(image: PreparedImagePayload, fallbackReason: String) async throws -> AnalysisResult {
    try await Task.sleep(nanoseconds: 1_000_000_000)
    return buildMockResult(from: "Mock image payload")
  }

  func analyze(qrPayload: String) async throws -> AnalysisResult {
    try await Task.sleep(nanoseconds: 500_000_000)
    return buildMockResult(from: qrPayload)
  }

  func fetchHistory() async throws -> [AnalysisResult] {
    return [buildMockResult(from: "History mock")]
  }

  private func buildMockResult(from text: String) -> AnalysisResult {
    return AnalysisResult(
      id: UUID(),
      verdict: .safe,
      score: 10,
      flagged: false,
      summary: "Local mock analysis",
      extractedText: text,
      findings: [
        Finding(type: "local_mock", value: "test", severity: "low", description: "Mock local analysis run.")
      ],
      flaggedUrls: [],
      meta: ScanMeta(ocrMethod: "local", ocrConfidence: 1.0, ocrFallback: false),
      analysisTimestamp: Date()
    )
  }
}
