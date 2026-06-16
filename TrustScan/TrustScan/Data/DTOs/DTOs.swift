import Foundation

// MARK: - Request DTO

struct ScanInDTO: Encodable {
  let image_base64: String
  let os: String
}

struct TextScanInDTO: Encodable {
  let text: String
  let os: String = "iOS"
}

struct QRScanInDTO: Encodable {
  let payload: String
  let os: String = "iOS"
}

// MARK: - Response DTO

struct ScanOutDTO: Decodable {
  let scan_id: String?
  let score: Int?
  let risk_score: Int?
  let flagged: Bool?
  let verdict: String?
  let findings: [FindingOutDTO]?
  let flagged_urls: [FlaggedUrlDTO]?
  let _meta: ScanMetaDTO?

  func toDomain() -> AnalysisResult {
    let resultFindings = findings?.map { f in
      Finding(type: f.type ?? "unknown", value: f.value ?? "", severity: f.severity ?? "low", description: f.description ?? "")
    } ?? []

    let resultMeta = _meta.map { m in
      ScanMeta(ocrMethod: m.ocr_method, ocrConfidence: m.ocr_confidence, ocrFallback: m.ocr_fallback)
    }

    let threatVerdict = ThreatVerdict(rawValue: verdict?.lowercased() ?? "") ?? .suspicious
    
    let extractedUrls = flagged_urls?.compactMap { $0.url } ?? []
    
    let finalScore = score ?? risk_score ?? 0

    return AnalysisResult(
      id: UUID(uuidString: scan_id ?? "") ?? UUID(),
      verdict: threatVerdict,
      score: finalScore,
      flagged: flagged ?? false,
      summary: "", // Kept empty as per new spec
      extractedText: "", // Kept empty as per new spec
      findings: resultFindings,
      flaggedUrls: extractedUrls,
      meta: resultMeta,
      analysisTimestamp: Date()
    )
  }
}

struct FlaggedUrlDTO: Decodable {
  let url: String
  
  init(from decoder: Decoder) throws {
    if let container = try? decoder.singleValueContainer(), let stringValue = try? container.decode(String.self) {
      self.url = stringValue
    } else if let container = try? decoder.container(keyedBy: CodingKeys.self), let urlValue = try? container.decode(String.self, forKey: .url) {
      self.url = urlValue
    } else {
      self.url = ""
    }
  }
  
  enum CodingKeys: String, CodingKey {
    case url
  }
}

struct FindingOutDTO: Decodable {
  let type: String?
  let value: String?
  let severity: String?
  let description: String?
}

struct ScanMetaDTO: Decodable {
  let ocr_method: String?
  let ocr_confidence: Double?
  let ocr_fallback: Bool?
}

// MARK: - Config DTO

struct ConfigOutDTO: Decodable {
  let scan_credit_cap: Int
  let ad_frequency: Int
  let sensitivity_threshold: Int
  let config_version: Int
}

// MARK: - Supabase Auth DTOs

struct SupabaseSignUpRequest: Encodable {
  let email: String
  let password: String
}

struct SupabaseSignInRequest: Encodable {
  let email: String
  let password: String
}

struct SupabaseAuthResponse: Decodable {
  let access_token: String?
  let refresh_token: String?
  let expires_in: Int?
  let user: SupabaseUser?
  let error: String?
  let error_description: String?
  let msg: String?
}

struct SupabaseUser: Decodable, Identifiable {
  let id: String
  let email: String?
  let created_at: String?
}

// MARK: - Mapping to Domain Models


extension ConfigOutDTO {
  func toDomain() -> AppConfiguration {
    AppConfiguration(
      maxImageFileSizeBytes: 8_000_000,
      maxImageDimension: 2_800,
      pollingIntervalSeconds: 2.0,
      pollingMaxAttempts: 10,
      supportedImageFormats: ["jpg", "jpeg", "png", "heic"],
      scanCreditCap: scan_credit_cap,
      sensitivityThreshold: sensitivity_threshold
    )
  }
}
