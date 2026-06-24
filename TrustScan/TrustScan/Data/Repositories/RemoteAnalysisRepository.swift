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
      image: base64String,           // field renamed to "image" per new contract
      os: "iOS",
      device_id: nil,                // APIClient sets X-Device-Id header; nil here is fine
      fallback_reason: fallbackReason
    )
    let response: ScanOutDTO = try await apiClient.post(path: "/api/v1/sandbox-image", body: request)
    return response.toDomain()
  }

  func analyze(qrPayload: String) async throws -> AnalysisResult {
    // QR codes use the dedicated /check-qr endpoint per new backend contract
    let request = QRScanInDTO(payload: qrPayload)
    let response: ScanOutDTO = try await apiClient.post(path: "/api/v1/check-qr", body: request)
    return response.toDomain()
  }

  func submitFeedback(scanId: String, label: String) async throws {
    let body = FeedbackInDTO(scan_id: scanId, label: label, reason: nil)
    let _: FeedbackOutDTO = try await apiClient.post(path: "/api/v1/feedback", body: body)
  }

}
