import SwiftUI

struct AnalysisResultView: View {
  let result: AnalysisResult
  let onShare: () -> Void

  @State private var selectedIndicator: ThreatIndicator?

  init(result: AnalysisResult, onShare: @escaping () -> Void = {}) {
    self.result = result
    self.onShare = onShare
  }

  var body: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.large) {
      // Verdict Header
      SectionCard {
        VStack(alignment: .leading, spacing: SpacingTokens.medium) {
          HStack(alignment: .center) {
            VerdictBadge(verdict: result.verdict)
            Spacer()
            Button("Share") { onShare() }
              .buttonStyle(.bordered)
          }

          Text(result.summary)
            .font(TypographyTokens.body)
            .foregroundStyle(ColorTokens.ik)

          Gauge(value: result.threatScore, in: 0...1) {
            Text("Risk Score")
          } currentValueLabel: {
            Text("\(Int(result.threatScore * 100))%")
              .font(TypographyTokens.sectionTitle)
              .foregroundStyle(result.verdict.tintColor)
          }
          .tint(result.verdict.tintColor)
          .accessibilityLabel("Risk score: \(Int(result.threatScore * 100)) percent")

          Text(riskDescription)
            .font(TypographyTokens.caption)
            .foregroundStyle(ColorTokens.st)
        }
      }

      // Flagged Indicators
      if !result.indicators.isEmpty {
        SectionCard(title: "What We Found") {
          ForEach(result.indicators) { indicator in
            Button {
              selectedIndicator = indicator
            } label: {
              VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
                HStack {
                  Text(indicator.title)
                    .font(TypographyTokens.sectionTitle)
                    .foregroundStyle(ColorTokens.ik)
                  Spacer()
                  Text(indicator.severity.rawValue.capitalized)
                    .font(TypographyTokens.caption)
                    .padding(.horizontal, SpacingTokens.small)
                    .padding(.vertical, 6)
                    .background(indicator.severity.tintColor.opacity(0.14))
                    .clipShape(Capsule())
                }

                Text(indicator.description)
                  .font(TypographyTokens.body)
                  .foregroundStyle(ColorTokens.st)
                  .multilineTextAlignment(.leading)

                if let rawValue = indicator.rawValue, !rawValue.isEmpty {
                  Text(rawValue)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(ColorTokens.st)
                }
              }
              .accessibilityLabel("\(indicator.title), severity: \(indicator.severity.rawValue)")
            }
            .buttonStyle(.plain)

            if indicator.id != result.indicators.last?.id {
              Divider()
            }
          }
        }
      }

      // Recommendations
      SectionCard(title: "What to Do") {
        ForEach(result.recommendations) { action in
          HStack(alignment: .top, spacing: SpacingTokens.small) {
            Image(systemName: "arrow.forward.circle.fill")
              .foregroundStyle(ColorTokens.acc)
            Text(action.actionText)
              .font(TypographyTokens.body)
              .foregroundStyle(ColorTokens.ik)
          }
        }
      }

      // Educational Context
      if let educationalContext = result.educationalContext {
        SectionCard(title: educationalContext.title) {
          Text(educationalContext.body)
            .font(TypographyTokens.body)
            .foregroundStyle(ColorTokens.st)
        }
      }

      // Extracted Text
      if !result.extractedText.isEmpty {
        SectionCard(title: "Extracted text") {
          Text(result.extractedText)
            .font(.system(.footnote, design: .monospaced))
            .foregroundStyle(ColorTokens.st)
        }
      }
    }
    .sheet(item: $selectedIndicator) { indicator in
      IndicatorDetailSheet(indicator: indicator)
    }
  }

  private var riskDescription: String {
    let score = Int(result.threatScore * 100)
    switch score {
    case 0...20: return "Very Low Risk"
    case 21...40: return "Low Risk"
    case 41...60: return "Moderate Risk"
    case 61...80: return "High Risk"
    default: return "Critical Risk"
    }
  }
}

// MARK: - Indicator Detail Sheet (S-09)

struct IndicatorDetailSheet: View {
  let indicator: ThreatIndicator
  @Environment(\.dismiss) private var dismiss

  var body: some View {
    NavigationStack {
      ScrollView {
        VStack(alignment: .leading, spacing: SpacingTokens.large) {
          // Header
          HStack(spacing: SpacingTokens.medium) {
            Image(systemName: iconFor(category: indicator.category))
              .font(.system(size: 40, weight: .semibold))
              .foregroundStyle(indicator.severity.tintColor)

            VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
              Text(indicator.title)
                .font(TypographyTokens.title)
                .foregroundStyle(ColorTokens.ik)

              Text(indicator.severity.rawValue.capitalized)
                .font(TypographyTokens.caption)
                .padding(.horizontal, SpacingTokens.small)
                .padding(.vertical, 4)
                .background(indicator.severity.tintColor.opacity(0.14))
                .clipShape(Capsule())
            }
          }

          Divider()

          // What Was Found
          if let raw = indicator.rawValue, !raw.isEmpty {
            VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
              Text("What We Found")
                .font(TypographyTokens.sectionTitle)
                .foregroundStyle(ColorTokens.ik)

              Text(raw)
                .font(.system(.body, design: .monospaced))
                .padding(SpacingTokens.medium)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                  RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(ColorTokens.sfm)
                )
            }
          }

          // Why Suspicious
          VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
            Text("Why This Is Suspicious")
              .font(TypographyTokens.sectionTitle)
              .foregroundStyle(ColorTokens.ik)

            Text(indicator.description)
              .font(TypographyTokens.body)
              .foregroundStyle(ColorTokens.st)
          }

          // What It Means
          VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
            Text("What It Could Mean")
              .font(TypographyTokens.sectionTitle)
              .foregroundStyle(ColorTokens.ik)

            Text(contextFor(category: indicator.category))
              .font(TypographyTokens.body)
              .foregroundStyle(ColorTokens.st)
          }
        }
        .padding(SpacingTokens.large)
      }
      .background(ColorTokens.bg.ignoresSafeArea())
      .navigationTitle("Indicator Detail")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .confirmationAction) {
          Button("Close") { dismiss() }
        }
      }
    }
    .presentationDetents([.medium, .large])
  }

  private func iconFor(category: ThreatCategory) -> String {
    switch category {
    case .urlThreat: return "link.badge.plus"
    case .impersonation: return "person.crop.circle.badge.exclamationmark"
    case .urgencyManipulation: return "clock.badge.exclamationmark"
    case .personalDataRequest: return "key.fill"
    case .paymentFraud: return "creditcard.trianglebadge.exclamationmark"
    case .unknownSender: return "person.fill.questionmark"
    case .maliciousContent: return "exclamationmark.shield.fill"
    case .socialEngineering: return "brain.head.profile"
    case .other: return "questionmark.circle"
    }
  }

  private func contextFor(category: ThreatCategory) -> String {
    switch category {
    case .urlThreat: return "Scam messages often include links that mimic legitimate websites. These links may steal your credentials or install malware."
    case .impersonation: return "Scammers frequently impersonate trusted brands or authorities to make their messages seem legitimate and urgent."
    case .urgencyManipulation: return "Creating a false sense of urgency is a core social engineering tactic. It pressures victims into acting before they can think critically."
    case .personalDataRequest: return "Legitimate organizations rarely ask for sensitive information like passwords or SSNs via text message or email."
    case .paymentFraud: return "Requests for gift cards, cryptocurrency, or wire transfers are almost always scam indicators, as these payment methods are difficult to trace or reverse."
    case .unknownSender: return "Messages from unknown numbers with urgent requests should be independently verified through official channels."
    case .maliciousContent: return "Content flagged as malicious may contain harmful code, links to phishing sites, or social engineering attempts."
    case .socialEngineering: return "Social engineering exploits human psychology — trust, fear, curiosity — to manipulate victims into taking harmful actions."
    case .other: return "This indicator was flagged based on pattern matching. Review the content carefully before taking any action."
    }
  }
}
