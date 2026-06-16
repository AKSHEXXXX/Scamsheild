import Foundation

protocol AnalysisRepositoryPort {
  func analyze(text: String) async throws -> AnalysisResult
  func analyze(image: PreparedImagePayload, fallbackReason: String) async throws -> AnalysisResult
  func analyze(qrPayload: String) async throws -> AnalysisResult
  func fetchHistory() async throws -> [AnalysisResult]
}
