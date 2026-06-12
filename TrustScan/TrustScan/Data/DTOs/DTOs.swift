import Foundation

// MARK: - Request DTO

struct ScanInDTO: Encodable {
  let image_base64: String
  let os: String
}

// MARK: - Response DTO

struct ScanOutDTO: Decodable {
  let scan_id: String
  let kind: String
  let risk_score: Int
  let verdict: String
  let warning_count: Int
  let extracted_text: String
  let findings: [FindingOutDTO]
  let flagged_urls: [FlaggedUrlDTO]
}

struct FindingOutDTO: Decodable {
  let type: String
  let severity: String
  let title: String
  let detail: String
}

struct FlaggedUrlDTO: Decodable {
  let url: String
  let final_url: String
  let reputation: String
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

extension ScanOutDTO {
  func toDomain() -> AnalysisResult {
    let score = min(Double(risk_score) / 100.0, 1.0)

    let domainVerdict: ThreatVerdict
    switch verdict.lowercased() {
    case "safe", "clean", "low_risk":
      domainVerdict = .safe
    case "suspicious", "warning", "medium_risk":
      domainVerdict = .suspicious
    case "dangerous", "scam", "malicious", "high_risk":
      domainVerdict = .dangerous
    default:
      domainVerdict = .inconclusive
    }

    var indicators: [ThreatIndicator] = []

    for finding in findings {
      let severityEnum: IndicatorSeverity
      switch finding.severity.lowercased() {
      case "high": severityEnum = .high
      case "medium": severityEnum = .medium
      default: severityEnum = .low
      }
      
      let category = categorize(type: finding.type)
      
      indicators.append(
        ThreatIndicator(
          id: UUID(),
          category: category,
          title: finding.title,
          description: finding.detail,
          severity: severityEnum,
          rawValue: finding.type
        )
      )
    }

    for flaggedUrl in flagged_urls {
      indicators.append(
        ThreatIndicator(
          id: UUID(),
          category: .urlThreat,
          title: "Flagged URL",
          description: "This URL was flagged as \(flaggedUrl.reputation). Final destination: \(flaggedUrl.final_url)",
          severity: flaggedUrl.reputation.lowercased() == "malicious" ? .high : .medium,
          rawValue: flaggedUrl.url
        )
      )
    }

    let summary = buildSummary(verdict: domainVerdict, findings: findings, urls: flagged_urls)
    let recommendations = buildRecommendations(verdict: domainVerdict, hasUrls: !flagged_urls.isEmpty, findings: findings)
    let education = educationalContent(for: domainVerdict)

    return AnalysisResult(
      id: UUID(),
      verdict: domainVerdict,
      threatScore: score,
      summary: summary,
      extractedText: extracted_text,
      indicators: indicators.sorted { severityWeight($0.severity) > severityWeight($1.severity) },
      recommendations: recommendations,
      analysisTimestamp: Date(),
      educationalContext: education
    )
  }

  private func categorize(type: String) -> ThreatCategory {
    let lower = type.lowercased()
    if ["urgency", "time"].contains(where: { lower.contains($0) }) {
      return .urgencyManipulation
    }
    if ["personal", "identity", "data"].contains(where: { lower.contains($0) }) {
      return .personalDataRequest
    }
    if ["payment", "money", "finance", "crypto"].contains(where: { lower.contains($0) }) {
      return .paymentFraud
    }
    if ["impersonation", "spoof"].contains(where: { lower.contains($0) }) {
      return .impersonation
    }
    return .socialEngineering
  }

  private func titleFor(category: ThreatCategory) -> String {
    switch category {
    case .urgencyManipulation: return "Urgency language"
    case .personalDataRequest: return "Sensitive information request"
    case .paymentFraud: return "Payment pressure"
    case .impersonation: return "Brand impersonation"
    case .urlThreat: return "Suspicious link"
    case .unknownSender: return "Unknown sender"
    case .maliciousContent: return "Malicious content"
    case .socialEngineering: return "Social engineering"
    case .other: return "Other indicator"
    }
  }

  private func severityWeight(_ severity: IndicatorSeverity) -> Int {
    switch severity {
    case .high: return 3
    case .medium: return 2
    case .low: return 1
    }
  }

  private func buildSummary(verdict: ThreatVerdict, findings: [FindingOutDTO], urls: [FlaggedUrlDTO]) -> String {
    switch verdict {
    case .dangerous:
      let topTypes = findings.prefix(3).map { $0.type }.joined(separator: ", ")
      return "This screenshot shows several high-risk scam traits including \(topTypes)."
    case .suspicious:
      return "This screenshot contains warning signs that deserve caution."
    case .safe:
      return "No clear scam traits stood out, but verify the sender before acting."
    case .inconclusive:
      return "The scan was only partially readable and needs a manual check."
    }
  }

  private func buildRecommendations(verdict: ThreatVerdict, hasUrls: Bool, findings: [FindingOutDTO]) -> [RecommendedAction] {
    var actions: [RecommendedAction] = []

    if verdict == .dangerous || verdict == .suspicious {
      actions.append(RecommendedAction(id: UUID(), priority: 1, actionText: "Do not tap links or reply until the sender is verified.", actionType: .informational))
    }
    if hasUrls {
      actions.append(RecommendedAction(id: UUID(), priority: 2, actionText: "Compare any link with the official domain before visiting.", actionType: .informational))
    }
    if findings.contains(where: { ["personal", "identity", "data", "login"].contains($0.type.lowercased()) }) {
      actions.append(RecommendedAction(id: UUID(), priority: 3, actionText: "Never share passwords, one-time codes, or identity details from a message like this.", actionType: .informational))
    }
    if actions.isEmpty {
      actions.append(RecommendedAction(id: UUID(), priority: 1, actionText: "If unsure, verify the sender independently before responding.", actionType: .informational))
    }
    return actions
  }

  private func educationalContent(for verdict: ThreatVerdict) -> EducationalContent {
    switch verdict {
    case .dangerous:
      return EducationalContent(title: "Why this matters", body: "Scam campaigns combine urgency, authority, and a shortcut to action. Slowing the decision down is the best first defense.")
    case .suspicious:
      return EducationalContent(title: "What to watch for", body: "Messages that push you outside your normal routine deserve extra scrutiny, especially involving links, codes, or money.")
    case .safe:
      return EducationalContent(title: "Healthy habit", body: "Even when a message looks okay, independent verification is still the safest response for anything important.")
    case .inconclusive:
      return EducationalContent(title: "Better scan quality helps", body: "Clear screenshots with the full message and sender details give the scanner more useful evidence.")
    }
  }
}

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
