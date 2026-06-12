import Foundation

protocol AnalysisRepositoryPort {
  func analyze(image: PreparedImagePayload) async throws -> AnalysisResult
}
