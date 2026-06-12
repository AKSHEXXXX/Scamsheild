import Foundation

struct SubmitAnalysisUseCase {
  private let analysisRepository: any AnalysisRepositoryPort

  init(analysisRepository: any AnalysisRepositoryPort) {
    self.analysisRepository = analysisRepository
  }

  func callAsFunction(image: PreparedImagePayload) async throws -> AnalysisResult {
    try await analysisRepository.analyze(image: image)
  }
}
