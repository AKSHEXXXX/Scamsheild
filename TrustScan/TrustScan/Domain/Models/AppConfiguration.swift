import Foundation

struct AppConfiguration: Codable, Hashable {
  let maxImageFileSizeBytes: Int
  let maxImageDimension: Int
  let pollingIntervalSeconds: Double
  let pollingMaxAttempts: Int
  let supportedImageFormats: [String]
  let scanCreditCap: Int
  let sensitivityThreshold: Int

  static let defaultValue = AppConfiguration(
    maxImageFileSizeBytes: 8_000_000,
    maxImageDimension: 2_800,
    pollingIntervalSeconds: 2.0,
    pollingMaxAttempts: 10,
    supportedImageFormats: ["jpg", "jpeg", "png", "heic"],
    scanCreditCap: 20,
    sensitivityThreshold: 50
  )
}

struct PreparedImagePayload: Hashable {
  let data: Data
  let mimeType: String
  let fileName: String
}
