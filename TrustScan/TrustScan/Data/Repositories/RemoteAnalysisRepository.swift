import Foundation

struct RemoteAnalysisRepository: AnalysisRepositoryPort {
  private let apiClient: APIClient

  init(apiClient: APIClient) {
    self.apiClient = apiClient
  }

  func analyze(image: PreparedImagePayload) async throws -> AnalysisResult {
    let base64String = image.data.base64EncodedString()
    let request = ScanInDTO(image_base64: base64String, os: "iOS")
    let response: ScanOutDTO = try await apiClient.post(path: "/api/v1/sandbox-image", body: request)
    return response.toDomain()
  }
}
