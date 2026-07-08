import Foundation

enum ThreatVerdict: String, Codable, CaseIterable, Hashable, Identifiable {
  case safe
  case suspicious
  case scam

  var id: String { rawValue }
}

// MARK: - Client-Side Scam Signal Detector
// Safety net for when backend models are degraded (e.g. Agent 1 TF-IDF offline).
// Checks extracted text for known multi-dimensional scam patterns.
struct ClientScamSignals {
  let policeImpersonation: Bool
  let urgency: Bool
  let financialRequest: Bool
  let otpRequest: Bool
  let threatLanguage: Bool
  let hindiScamPatterns: Bool
  let homoglyphUrl: Bool
  let urlShortener: Bool   // flagged_urls or text contains a known URL shortener

  var triggeredCount: Int {
    [policeImpersonation, urgency, financialRequest,
     otpRequest, threatLanguage, hindiScamPatterns, homoglyphUrl, urlShortener]
      .filter { $0 }.count
  }

  // If ≥3 client-side dimensions fire on a backend-safe result, the backend likely missed it
  var isSuspectedMiss: Bool { triggeredCount >= 3 }

  // Strongest escalation: impersonation + threat + financial all together
  var isHighConfidenceMiss: Bool {
    policeImpersonation && threatLanguage && (financialRequest || otpRequest)
  }

  static func analyse(text: String, flaggedUrls: [String]) -> ClientScamSignals {
    let t = text.lowercased()

    let policeWords = ["police", "cbi", "cyber cell", "cybercell", "rbi", "income tax",
                       "enforcement directorate", "ed officer", "inspector"]
    let urgencyWords = ["urgent", "immediately", "within 24 hours", "act now",
                        "last warning", "final notice", "turant", "jaldi", "abhi"]
    let financialWords = ["transfer", "send money", "pay now", "wire", "account number",
                          "bank details", "₹", "rs.", "lakh", "scammer@", "@paytm",
                          "@phonepe", "@gpay", "upi"]
    let otpWords = ["otp", "one time password", "verification code", "share the otp",
                    "enter the otp", "share otp", "otp dalein"]
    let threatWords = ["arrest", "warrant", "legal action", "suspended", "blocked",
                       "frozen", "banned", "case registered", "giraftaar", "band ho jayega"]
    let hindiScamWords = ["aapka account", "turant verify", "aadhaar block", "band ho jayega",
                          "kyc update", "link par click", "paisa bhejein"]

    // Homoglyph URL check: known brand name with digit/letter substitution
    let homoglyphPatterns = ["amaz0n", "g00gle", "paypa1", "micros0ft",
                              "app1e", "faceb00k", "hdfc", "icici"]
    let hasHomoglyphUrl = flaggedUrls.contains { url in
      let u = url.lowercased()
      return homoglyphPatterns.contains { u.contains($0) }
    } || homoglyphPatterns.contains { t.contains($0) }

    // URL shortener check — scammers use shorteners to hide phishing destinations
    let shortenerDomains = ["bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly",
                             "is.gd", "buff.ly", "rb.gy", "cutt.ly", "short.io"]
    let hasShortener = flaggedUrls.contains { url in
      let u = url.lowercased()
      return shortenerDomains.contains { u.contains($0) }
    } || shortenerDomains.contains { t.contains($0) }

    return ClientScamSignals(
      policeImpersonation: policeWords.contains { t.contains($0) },
      urgency: urgencyWords.contains { t.contains($0) },
      financialRequest: financialWords.contains { t.contains($0) },
      otpRequest: otpWords.contains { t.contains($0) },
      threatLanguage: threatWords.contains { t.contains($0) },
      hindiScamPatterns: hindiScamWords.contains { t.contains($0) },
      homoglyphUrl: hasHomoglyphUrl,
      urlShortener: hasShortener
    )
  }
}

struct Finding: Codable, Hashable {
  let type: String
  let value: String
  let severity: String
  let description: String
}

struct ScanMeta: Codable, Hashable {
  let ocrMethod: String?
  let ocrConfidence: Double?
  let ocrFallback: Bool?
}

struct AnalysisResult: Identifiable, Codable, Hashable {
  let id: UUID
  let backendScanId: String?         // raw scan_id string from backend; nil for local/fallback results
  let verdict: ThreatVerdict
  let score: Int
  let flagged: Bool
  let summary: String
  let extractedText: String
  let findings: [Finding]
  let flaggedUrls: [String]
  let topSignal: String?
  let warningCount: Int
  let meta: ScanMeta?
  let analysisTimestamp: Date
  // Transient — not persisted in history. Set by toDomain() when Agent 1 returns null.
  var backendDegraded: Bool = false

  // Exclude backendDegraded from Codable so old history entries decode without error.
  private enum CodingKeys: String, CodingKey {
    case id, backendScanId, verdict, score, flagged, summary, extractedText,
         findings, flaggedUrls, topSignal, warningCount, meta, analysisTimestamp
  }

  // Client-side signals computed from extractedText + flaggedUrls
  var clientSignals: ClientScamSignals {
    ClientScamSignals.analyse(text: extractedText, flaggedUrls: flaggedUrls)
  }

  // True if backend returned safe/low-risk but client detects multiple red flags
  var clientDetectedMiss: Bool {
    verdict == .safe && clientSignals.isSuspectedMiss
  }

  // True if score is near a threshold boundary (±10 points) — result is uncertain
  var isBorderlineScore: Bool {
    (score >= 20 && score <= 40) || (score >= 60 && score <= 68)
  }

  // Effective verdict: escalates if client override fires or backend is known degraded
  var effectiveVerdict: ThreatVerdict {
    if clientSignals.isHighConfidenceMiss && verdict == .safe {
      return .scam
    }
    // When Agent 1 was offline, lower the bar: ≥2 client dimensions → suspicious
    if backendDegraded && clientSignals.triggeredCount >= 2 && verdict == .safe {
      return .suspicious
    }
    if clientSignals.isSuspectedMiss && verdict == .safe {
      return .suspicious
    }
    return verdict
  }

  var contextualSummary: String {
    switch verdict {
    case .safe:
      // Client-side override message when backend likely missed a scam
      if clientSignals.isHighConfidenceMiss {
        return "Our scanner returned a low score (\(score)%), but this message contains police/authority impersonation, financial demands, and threats — a known digital arrest scam pattern. Do not comply. Block and report the sender."
      }
      if clientSignals.isSuspectedMiss {
        return "The risk score is \(score)%, but multiple scam indicators were detected locally (\(clientSignals.triggeredCount) patterns). The analysis may be incomplete. Exercise caution and verify the sender independently before taking any action."
      }
      if isBorderlineScore && !findings.isEmpty {
        return "Risk score is \(score)% — this is a borderline result. Some suspicious patterns were detected but not enough to flag definitively. Treat with caution and do not share personal information."
      }
      if flaggedUrls.isEmpty && findings.isEmpty {
        return "No scam patterns found. This content scored \(score)% — well within safe limits. You can engage with it normally."
      } else if !flaggedUrls.isEmpty {
        let n = flaggedUrls.count
        return "This content scored \(score)% — low risk overall. However, \(n) shortened or suspicious link\(n == 1 ? "" : "s") \(n == 1 ? "was" : "were") detected, which \(n == 1 ? "is" : "are") commonly used to hide malicious destinations. Do not click unless you fully trust the source."
      } else {
        let n = findings.count
        return "Risk level is low at \(score)%. \(n) minor indicator\(n == 1 ? "" : "s") \(n == 1 ? "was" : "were") flagged — likely not dangerous, but review the details below before proceeding."
      }
    case .suspicious:
      if let signal = topSignal {
        let name = signal.replacingOccurrences(of: "_", with: " ").capitalized
        return "\(name) was detected in this content, pushing the risk score to \(score)%. This is a common tactic used in phishing and fraud messages. Do not share personal information or click any links until you have verified the source independently."
      }
      return "Several suspicious patterns were detected (risk score: \(score)%). This content shows characteristics commonly found in scam messages. Proceed with caution — verify the sender independently before taking any action."
    case .scam:
      if let signal = topSignal {
        let name = signal.replacingOccurrences(of: "_", with: " ").capitalized
        return "High-confidence scam detected — \(name) found with a risk score of \(score)%. This is a known fraud pattern. Do not respond, click any links, or share personal or financial information. Block and report the sender."
      }
      return "High-risk content detected (score: \(score)%). Multiple scam indicators are present in this message. Do not engage — block and report the sender immediately."
    }
  }
}
