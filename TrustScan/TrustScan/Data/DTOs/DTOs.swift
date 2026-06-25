import Foundation

// MARK: - Request DTO

struct ScanInDTO: Encodable {
  let image: String           // was image_base64 — contract field name is "image"
  let os: String
  let device_id: String?
  let fallback_reason: String?
}

struct TextScanInDTO: Encodable {
  let text: String
  let os: String = "iOS"
}

struct QRScanInDTO: Encodable {
  let payload: String
  let os: String = "iOS"
}

struct URLScanInDTO: Encodable {
  let url: String
  let os: String = "iOS"
}

struct FeedbackInDTO: Encodable {
  let scan_id: String
  let label: String     // "scam" or "legit"
  let reason: String?
}

struct FeedbackOutDTO: Decodable {
  let ok: Bool?  // Optional — backend response shape may vary; any 2xx is treated as success
}

// MARK: - Response DTO

struct ScanOutDTO: Decodable {
  // Stable contract fields (only rely on these per backend spec)
  let scan_id: String?
  let kind: String?
  let flagged: Bool?
  let scam_score: Int?        // canonical score field per new spec
  let verdict: String?        // low_risk | suspicious | high_risk
  let top_signal: String?
  let warning_count: Int?
  let findings: [FindingOutDTO]?
  let flagged_urls: [FlaggedUrlDTO]?
  // Image-specific stable fields
  let extracted_text: String?
  let meta: ScanMetaDTO?

  func toDomain() -> AnalysisResult {
    let resultFindings = findings?.map { f in
      // Backend spec uses "message" field; "description" kept as fallback
      Finding(
        type: f.type ?? "unknown",
        value: f.value ?? "",
        severity: f.severity ?? "low",
        description: f.message ?? f.description ?? ""
      )
    } ?? []

    let resultMeta = meta.map { m in
      ScanMeta(ocrMethod: m.ocr_method, ocrConfidence: m.ocr_confidence, ocrFallback: m.ocr_fallback)
    }

    // Map backend verdict strings → domain enum
    // Backend: low_risk → safe, suspicious → suspicious, high_risk → scam
    let threatVerdict: ThreatVerdict
    switch verdict?.lowercased() {
    case "low_risk", "safe":   threatVerdict = .safe
    case "high_risk", "scam":  threatVerdict = .scam
    default:                   threatVerdict = .suspicious
    }

    let extractedUrls = flagged_urls?.compactMap { $0.url }.filter { !$0.isEmpty } ?? []

    return AnalysisResult(
      id: UUID(uuidString: scan_id ?? "") ?? UUID(),
      backendScanId: scan_id,
      verdict: threatVerdict,
      score: scam_score ?? 0,
      flagged: flagged ?? false,
      summary: "",
      extractedText: extracted_text ?? "",
      findings: resultFindings,
      flaggedUrls: extractedUrls,
      topSignal: top_signal,
      warningCount: warning_count ?? 0,
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
  let message: String?       // canonical per new spec
  let description: String?   // kept as fallback
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
