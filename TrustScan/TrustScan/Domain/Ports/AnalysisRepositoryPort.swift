import Foundation

protocol AnalysisRepositoryPort {
  func analyze(text: String) async throws -> AnalysisResult
  func analyze(image: PreparedImagePayload, fallbackReason: String) async throws -> AnalysisResult
  func analyze(qrPayload: String) async throws -> AnalysisResult
  func submitFeedback(scanId: String, label: String) async throws
}
