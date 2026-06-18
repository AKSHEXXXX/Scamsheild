import Foundation

struct RemoteAnalysisRepository: AnalysisRepositoryPort {
  private let apiClient: APIClient

  init(apiClient: APIClient) {
    self.apiClient = apiClient
  }

  func analyze(text: String) async throws -> AnalysisResult {
    let request = TextScanInDTO(text: text)
    let response: ScanOutDTO = try await apiClient.post(path: "/api/v1/analyze-text", body: request)
    return response.toDomain()
  }

  func analyze(image: PreparedImagePayload, fallbackReason: String) async throws -> AnalysisResult {
    let base64String = image.data.base64EncodedString()
    
    let request = ScanInDTO(
        image_base64: base64String,
        os: "iOS"
    )
    let response: ScanOutDTO = try await apiClient.post(path: "/api/v1/sandbox-image", body: request)
    return response.toDomain()
  }

  func analyze(qrPayload: String) async throws -> AnalysisResult {
    let request = TextScanInDTO(text: qrPayload)
    let response: ScanOutDTO = try await apiClient.post(path: "/api/v1/analyze-text", body: request)
    return response.toDomain()
  }

}
