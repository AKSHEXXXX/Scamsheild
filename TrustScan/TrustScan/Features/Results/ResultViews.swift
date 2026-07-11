import SwiftUI
import UIKit

private func agentDisplayLabel(for signal: String?) -> String {
  guard let signal else { return "AI Analysis" }
  let labelMap: [String: String] = [
    "text_tfidf_prob": "Text Analysis",
    "text_distilbert_prob": "Text Analysis",
    "text_prob": "Text Analysis",
    "url_prob": "Link Analysis",
    "qr_url_prob": "QR Analysis",
    "upi_rule_score": "Payment Analysis",
    "upi_xgb_prob": "Payment Analysis",
    "brand_flag": "Brand Check",
    "malware_prob": "Malware Analysis",
    "regex_score": "Pattern Analysis",
    "deepfake_prob": "Media Analysis",
    "audio_transcript_prob": "Audio Analysis",
  ]
  return labelMap[signal] ?? "AI Analysis"
}

private func severityColor(_ severity: String) -> Color {
  switch severity.lowercased() {
  case "high": return ColorTokens.dng
  case "medium": return ColorTokens.sus
  case "low": return ColorTokens.sfe
  default: return ColorTokens.st
  }
}

struct AnalysisResultView: View {
  let result: AnalysisResult
  let onShare: () -> Void
  let onFeedback: ((String, @escaping (Bool) -> Void) -> Void)?   // nil = hide feedback bar

  @State private var selectedFinding: Finding?
  @State private var feedbackState: FeedbackBarView.State = .idle
  @State private var showFeedbackSheet = false
  @State private var feedbackSheetDismissed = false
  @State private var showToast = false
  @State private var toastMessage = ""

  init(
    result: AnalysisResult,
    onShare: @escaping () -> Void = {},
    onFeedback: ((String, @escaping (Bool) -> Void) -> Void)? = nil
  ) {
    self.result = result
    self.onShare = onShare
    self.onFeedback = onFeedback
  }

  @State private var animatedScore: Double = 0

  var body: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.large) {
      // Result Header Card
      VStack(alignment: .leading, spacing: SpacingTokens.medium) {

        // Share button top-right
        HStack {
          Spacer()
          Button {
            AnalyticsManager.shared.capture(event: "report_shared", properties: [
                "result": result.verdict.rawValue,
                "threat_score": result.score
            ])
            onShare()
          } label: {
            Image(systemName: "square.and.arrow.up")
              .font(.system(size: 15, weight: .semibold))
              .foregroundStyle(ColorTokens.acc)
              .frame(minWidth: 44, minHeight: 44)
              .background(ColorTokens.acc.opacity(0.1))
              .clipShape(Circle())
          }
          .accessibilityLabel("Share result")
          .accessibilityHint("Opens the share sheet")
        }

        // Icon + Verdict title
        // Uses effectiveVerdict which escalates when client-side signals override backend
        HStack(spacing: SpacingTokens.small) {
          Image(systemName: result.effectiveVerdict.iconName)
            .font(.system(size: 40, weight: .semibold))
            .foregroundStyle(result.effectiveVerdict.tintColor)
            .accessibilityHidden(true)
          VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 6) {
              Text(result.effectiveVerdict.displayTitle)
                .font(.system(size: 22, weight: .bold, design: .rounded))
                .foregroundStyle(result.effectiveVerdict.tintColor)
              // Badge shown when client overrides backend verdict
              if result.effectiveVerdict != result.verdict {
                Text("On-device")
                  .font(.system(size: 10, weight: .bold))
                  .foregroundStyle(.white)
                  .padding(.horizontal, 6)
                  .padding(.vertical, 2)
                  .background(ColorTokens.dng)
                  .clipShape(Capsule())
                  .accessibilityLabel("On-device detection overrode server result")
              }
            }
            if let signal = result.topSignal {
              Text("Detected by: \(agentDisplayLabel(for: signal))")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(result.effectiveVerdict.tintColor)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(result.effectiveVerdict.tintColor.opacity(0.12))
                .clipShape(Capsule())
            }
          }
        }

        // Large centred score gauge — prominent centrepiece
        ZStack {
          Circle()
            .stroke(Color.gray.opacity(0.12), lineWidth: 16)
          Circle()
            .trim(from: 0, to: CGFloat(animatedScore) / 100.0)
            .stroke(
              AngularGradient(
                gradient: Gradient(colors: [result.effectiveVerdict.tintColor.opacity(0.5), result.effectiveVerdict.tintColor]),
                center: .center,
                startAngle: .degrees(-90),
                endAngle: .degrees(270)
              ),
              style: StrokeStyle(lineWidth: 16, lineCap: .round)
            )
            .rotationEffect(.degrees(-90))
            .shadow(color: result.effectiveVerdict.tintColor.opacity(0.4), radius: 10)
          VStack(spacing: 4) {
            Text("Risk Score")
              .font(TypographyTokens.caption)
              .foregroundStyle(ColorTokens.st)
              .textCase(.uppercase)
            Text("\(Int(animatedScore))%")
              .font(.system(size: 48, weight: .bold, design: .rounded))
              .foregroundStyle(result.effectiveVerdict.tintColor)
              .contentTransition(.numericText())
              .dynamicTypeSize(...DynamicTypeSize.accessibility2)
          }
        }
        .frame(width: 160, height: 160)
        .frame(maxWidth: .infinity)
        .padding(.vertical, SpacingTokens.small)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Risk score \(result.score) percent")

        // Stats chips row — below the gauge
        ScrollView(.horizontal, showsIndicators: false) {
          HStack(spacing: SpacingTokens.small) {
            if result.warningCount > 0 {
              statChip(
                icon: "exclamationmark.triangle.fill",
                label: "\(result.warningCount) warning\(result.warningCount == 1 ? "" : "s")",
                color: ColorTokens.sus
              )
            }
            if !result.flaggedUrls.isEmpty {
              statChip(
                icon: "link.badge.plus",
                label: "\(result.flaggedUrls.count) flagged link\(result.flaggedUrls.count == 1 ? "" : "s")",
                color: ColorTokens.dng
              )
            }
            if !result.findings.isEmpty {
              statChip(
                icon: "exclamationmark.shield.fill",
                label: "\(result.findings.count) indicator\(result.findings.count == 1 ? "" : "s") found",
                color: result.verdict.tintColor
              )
            }
            if result.warningCount == 0 && result.flaggedUrls.isEmpty && result.findings.isEmpty {
              statChip(icon: "checkmark.shield.fill", label: "No threats detected", color: ColorTokens.sfe)
            }
          }
        }

        Divider()
          .padding(.vertical, SpacingTokens.xSmall)

        // Contextual summary — below the gauge and chips
        // Uses effectiveVerdict-aware summary which incorporates client-side overrides
        Text(result.contextualSummary)
          .font(TypographyTokens.body)
          .foregroundStyle(ColorTokens.ik)
          .fixedSize(horizontal: false, vertical: true)
          .frame(maxWidth: .infinity, alignment: .leading)
      }
      .padding(SpacingTokens.large)
      .background(
        RoundedRectangle(cornerRadius: 24, style: .continuous)
          .fill(ColorTokens.sfm)
          .shadow(color: Color.black.opacity(0.04), radius: 12, x: 0, y: 6)
      )

      // Backend degraded warning — shown when primary text model was offline
      if result.backendDegraded {
        AgentDegradedWarning()
      }

      // Client-side override warning — shown when backend likely missed a scam
      if result.clientDetectedMiss {
        ClientOverrideWarningCard(signals: result.clientSignals)
      }

      // Borderline score warning — shown when result is near threshold boundary
      if result.isBorderlineScore && !result.clientDetectedMiss && !result.backendDegraded {
        BorderlineScoreWarning(score: result.score)
      }

      // Flagged URLs
      if !result.flaggedUrls.isEmpty {
        VStack(alignment: .leading, spacing: SpacingTokens.medium) {
          Text("Flagged Links")
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)
            .padding(.horizontal, 4)

          ForEach(result.flaggedUrls, id: \.self) { url in
            HStack(spacing: 12) {
              ZStack {
                Circle()
                  .fill(ColorTokens.dng.opacity(0.15))
                  .frame(width: 36, height: 36)
                Image(systemName: "link.badge.plus")
                  .foregroundStyle(ColorTokens.dng)
                  .font(.system(size: 14, weight: .bold))
                  .accessibilityHidden(true)
              }

              Text(url)
                .font(.system(.subheadline, design: .monospaced))
                .foregroundStyle(ColorTokens.ik)
                .lineLimit(1)
                .truncationMode(.middle)

              Spacer()
            }
            .padding(12)
            .background(
              RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(ColorTokens.sf)
                .shadow(color: Color.black.opacity(0.03), radius: 6, x: 0, y: 2)
            )
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Flagged link \(url)")
          }
        }
      }

      // Findings
      if !result.findings.isEmpty {
        VStack(alignment: .leading, spacing: SpacingTokens.medium) {
          Text("Threat Indicators")
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)
            .padding(.horizontal, 4)

          VStack(spacing: SpacingTokens.small) {
            ForEach(result.findings, id: \.self) { finding in
              Button {
                selectedFinding = finding
              } label: {
                HStack(alignment: .top, spacing: SpacingTokens.medium) {
                  Image(systemName: "exclamationmark.shield.fill")
                    .font(.system(size: 24))
                    .foregroundStyle(severityColor(finding.severity))
                    .padding(.top, 2)
                    .accessibilityHidden(true)

                  VStack(alignment: .leading, spacing: 4) {
                    HStack {
                      Text(finding.type.capitalized.replacingOccurrences(of: "_", with: " "))
                        .font(.system(size: 16, weight: .bold))
                        .foregroundStyle(ColorTokens.ik)
                      Spacer()
                      Text(finding.severity.capitalized)
                        .font(.system(size: 11, weight: .bold))
                        .textCase(.uppercase)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(severityColor(finding.severity).opacity(0.15))
                        .foregroundStyle(severityColor(finding.severity))
                        .clipShape(Capsule())
                    }

                    Text(finding.description)
                      .font(TypographyTokens.caption)
                      .foregroundStyle(ColorTokens.st)
                      .multilineTextAlignment(.leading)
                      .lineLimit(2)
                  }
                }
                .padding(16)
                .background(
                  RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(ColorTokens.sf)
                    .shadow(color: Color.black.opacity(0.03), radius: 6, x: 0, y: 2)
                )
              }
              .buttonStyle(.plain)
              .accessibilityLabel("\(finding.type.capitalized.replacingOccurrences(of: "_", with: " ")), \(finding.severity) severity. \(finding.description)")
              .accessibilityHint("Shows finding details")
            }
          }
        }
      }

      // Feedback bar — only shown when the backend returned a real scan_id to correlate against
      if let onFeedback {
        FeedbackBarView(state: $feedbackState) { label in
          feedbackState = .sending
          onFeedback(label) { success in
            DispatchQueue.main.async {
              feedbackState = success ? .submitted : .failed
            }
          }
        }
      }

      // What to do now — only for HIGH_RISK and SUSPICIOUS
      if result.effectiveVerdict != .safe {
        VStack(alignment: .leading, spacing: SpacingTokens.medium) {
          Text("What to do now")
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)
            .padding(.horizontal, 4)

          VStack(spacing: SpacingTokens.small) {
            actionRow(icon: "hand.raised.fill", title: "Block this sender") {
              toastMessage = "Sender blocked"
              withAnimation { showToast = true }
            }
            actionRow(icon: "link.slash.fill", title: "Don't click any links") {
              toastMessage = "Stay safe — avoid clicking any links in the message"
              withAnimation { showToast = true }
            }
            actionRow(icon: "exclamationmark.bubble.fill", title: "Report to TRAI (India)") {
              if let url = URL(string: "https://sancharsaathi.gov.in") {
                UIApplication.shared.open(url)
              }
            }
          }
        }
      }
    }
    .onAppear {
      AnalyticsManager.shared.capture(event: "report_viewed", properties: [
          "result": result.verdict.rawValue,
          "threat_score": result.score
      ])
      AnalyticsManager.shared.screen(name: "Result")
      withAnimation(.spring(response: 1.5, dampingFraction: 0.8, blendDuration: 0)) {
        animatedScore = Double(result.score)
      }

      // Haptic feedback
      switch result.effectiveVerdict {
      case .scam:
        UINotificationFeedbackGenerator().notificationOccurred(.warning)
      case .suspicious:
        UINotificationFeedbackGenerator().notificationOccurred(.error)
      case .safe:
        UINotificationFeedbackGenerator().notificationOccurred(.success)
      }

      // Feedback sheet after 3 seconds
      if !feedbackSheetDismissed {
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
          if !feedbackSheetDismissed {
            showFeedbackSheet = true
          }
        }
      }
    }
    .sheet(item: Binding(
      get: { selectedFinding.map { FindingIdentifiableWrapper(finding: $0) } },
      set: { selectedFinding = $0?.finding }
    )) { wrapper in
      FindingDetailSheet(finding: wrapper.finding)
    }
    .sheet(isPresented: $showFeedbackSheet) {
      feedbackBottomSheet
    }
    .overlay(alignment: .bottom) {
      if showToast {
        Text(toastMessage)
          .font(TypographyTokens.caption)
          .foregroundStyle(.white)
          .padding(.horizontal, SpacingTokens.large)
          .padding(.vertical, SpacingTokens.small)
          .background(Color.black.opacity(0.8))
          .clipShape(Capsule())
          .padding(.bottom, 100)
          .transition(.move(edge: .bottom).combined(with: .opacity))
          .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
              withAnimation { showToast = false }
            }
          }
      }
    }
  }

  private func statChip(icon: String, label: String, color: Color) -> some View {
    HStack(spacing: 6) {
      Image(systemName: icon)
        .font(.system(size: 12, weight: .semibold))
        .foregroundStyle(color)
        .accessibilityHidden(true)
      Text(label)
        .font(.system(size: 13, weight: .medium, design: .rounded))
        .foregroundStyle(ColorTokens.ik)
    }
    .padding(.horizontal, 10)
    .padding(.vertical, 6)
    .background(color.opacity(0.1))
    .clipShape(Capsule())
    .accessibilityElement(children: .ignore)
    .accessibilityLabel(label)
  }

  private func actionRow(icon: String, title: String, action: @escaping () -> Void) -> some View {
    Button(action: action) {
      HStack(spacing: SpacingTokens.medium) {
        Image(systemName: icon)
          .font(.system(size: 16, weight: .semibold))
          .foregroundStyle(result.effectiveVerdict.tintColor)
          .frame(width: 24)
        Text(title)
          .font(.system(size: 15, weight: .semibold, design: .rounded))
          .foregroundStyle(ColorTokens.ik)
        Spacer()
        Image(systemName: "chevron.right")
          .font(.system(size: 13, weight: .semibold))
          .foregroundStyle(ColorTokens.st.opacity(0.5))
      }
      .padding(SpacingTokens.medium)
      .background(ColorTokens.sf)
      .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
    .buttonStyle(.plain)
    .accessibilityLabel(title + " action")
}

private var feedbackBottomSheet: some View {
    VStack(spacing: SpacingTokens.medium) {
      Text("Was this helpful?")
        .font(TypographyTokens.sectionTitle)
        .foregroundStyle(ColorTokens.ik)

      HStack(spacing: SpacingTokens.medium) {
        Button {
          onFeedback?("scam") { _ in }
          showFeedbackSheet = false
          feedbackSheetDismissed = true
        } label: {
          Label("This was a scam", systemImage: "exclamationmark.octagon.fill")
            .font(.system(size: 14, weight: .semibold, design: .rounded))
            .foregroundStyle(ColorTokens.dng)
            .frame(maxWidth: .infinity, minHeight: 44)
            .background(ColorTokens.dng.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(.plain)

        Button {
          onFeedback?("legit") { _ in }
          showFeedbackSheet = false
          feedbackSheetDismissed = true
        } label: {
          Label("This was safe", systemImage: "checkmark.shield.fill")
            .font(.system(size: 14, weight: .semibold, design: .rounded))
            .foregroundStyle(ColorTokens.sfe)
            .frame(maxWidth: .infinity, minHeight: 44)
            .background(ColorTokens.sfe.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(.plain)
      }
    }
    .padding(SpacingTokens.large)
    .presentationDetents([.height(180)])
  }
}

// MARK: - Share Card Generator

func shareCardImage(result: AnalysisResult) -> UIImage? {
  let cardColor: UIColor = result.effectiveVerdict == .scam ? UIColor(red: 0.9, green: 0.22, blue: 0.22, alpha: 1) : UIColor(ColorTokens.acc)
  let cardSize = CGSize(width: 360, height: 480)

  let renderer = UIGraphicsImageRenderer(size: cardSize)
  return renderer.image { ctx in
    let rect = CGRect(origin: .zero, size: cardSize)
    ctx.cgContext.setFillColor(cardColor.cgColor)
    ctx.cgContext.fill(rect)

    let textColor: UIColor = .white

    // Logo area
    let logoAttributes: [NSAttributedString.Key: Any] = [
      .font: UIFont.systemFont(ofSize: 20, weight: .bold),
      .foregroundColor: textColor.withAlphaComponent(0.9)
    ]
    let logoString = "TrustScan"
    logoString.draw(at: CGPoint(x: 24, y: 24), withAttributes: logoAttributes)

    // Verdict label
    let verdictAttributes: [NSAttributedString.Key: Any] = [
      .font: UIFont.systemFont(ofSize: 32, weight: .heavy),
      .foregroundColor: textColor
    ]
    let verdictString = result.effectiveVerdict.displayTitle
    verdictString.draw(at: CGPoint(x: 24, y: 200), withAttributes: verdictAttributes)

    // Score
    let scoreAttributes: [NSAttributedString.Key: Any] = [
      .font: UIFont.systemFont(ofSize: 64, weight: .bold),
      .foregroundColor: textColor
    ]
    let scoreString = "\(result.score)%"
    scoreString.draw(at: CGPoint(x: 24, y: 250), withAttributes: scoreAttributes)

    // Tagline
    let taglineAttributes: [NSAttributedString.Key: Any] = [
      .font: UIFont.systemFont(ofSize: 14, weight: .medium),
      .foregroundColor: textColor.withAlphaComponent(0.8)
    ]
    let taglineString = "Checked with TrustScan \u{00B7} trustscan.app"
    taglineString.draw(at: CGPoint(x: 24, y: 420), withAttributes: taglineAttributes)
  }
}

// Wrapper for Identifiable conformance
struct FindingIdentifiableWrapper: Identifiable {
  let id = UUID()
  let finding: Finding
}

// MARK: - Feedback Bar

struct FeedbackBarView: View {
  enum State { case idle, sending, submitted, failed }

  @Binding var state: State
  let onSubmit: (String) -> Void   // "scam" or "legit"

  var body: some View {
    VStack(spacing: SpacingTokens.small) {
      switch state {
      case .idle, .failed:
        Text("Was this result accurate?")
          .font(TypographyTokens.caption)
          .foregroundStyle(ColorTokens.st)

        if case .failed = state {
          Text("Couldn't submit — tap to retry")
            .font(.system(size: 11, weight: .medium))
            .foregroundStyle(ColorTokens.dng)
        }

        HStack(spacing: SpacingTokens.small) {
          feedbackButton(
            label: "This was a scam",
            icon: "exclamationmark.octagon.fill",
            color: ColorTokens.dng,
            value: "scam"
          )
          feedbackButton(
            label: "This was safe",
            icon: "checkmark.shield.fill",
            color: ColorTokens.sfe,
            value: "legit"
          )
        }

      case .sending:
        HStack(spacing: SpacingTokens.small) {
          ProgressView()
            .tint(ColorTokens.acc)
          Text("Submitting…")
            .font(TypographyTokens.caption)
            .foregroundStyle(ColorTokens.st)
        }

      case .submitted:
        HStack(spacing: SpacingTokens.xSmall) {
          Image(systemName: "checkmark.circle.fill")
            .foregroundStyle(ColorTokens.sfe)
            .accessibilityHidden(true)
          Text("Thanks for the feedback!")
            .font(.system(size: 13, weight: .semibold, design: .rounded))
            .foregroundStyle(ColorTokens.ik)
        }
      }
    }
    .frame(maxWidth: .infinity)
    .padding(SpacingTokens.medium)
    .background(
      RoundedRectangle(cornerRadius: 16, style: .continuous)
        .fill(ColorTokens.sfm)
        .shadow(color: Color.black.opacity(0.03), radius: 6, x: 0, y: 2)
    )
    .animation(.easeInOut(duration: 0.2), value: state == .submitted)
  }

  @ViewBuilder
  private func feedbackButton(label: String, icon: String, color: Color, value: String) -> some View {
    Button {
      onSubmit(value)
    } label: {
      HStack(spacing: 6) {
        Image(systemName: icon)
          .font(.system(size: 13, weight: .semibold))
          .accessibilityHidden(true)
        Text(label)
          .font(.system(size: 13, weight: .semibold, design: .rounded))
      }
      .foregroundStyle(color)
      .frame(maxWidth: .infinity)
      .padding(.vertical, 10)
      .background(color.opacity(0.1))
      .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
    .buttonStyle(.plain)
    .accessibilityLabel(label)
  }
}

extension FeedbackBarView.State: Equatable {}

// MARK: - Finding Detail Sheet

struct FindingDetailSheet: View {
  let finding: Finding
  @Environment(\.dismiss) private var dismiss

  var body: some View {
    NavigationStack {
      ScrollView {
        VStack(alignment: .leading, spacing: SpacingTokens.large) {
          // Header
          HStack(spacing: SpacingTokens.medium) {
            Image(systemName: "exclamationmark.triangle.fill")
              .font(.system(size: 40, weight: .semibold))
              .foregroundStyle(severityColor(finding.severity))
              .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
              Text(finding.type.capitalized.replacingOccurrences(of: "_", with: " "))
                .font(TypographyTokens.title)
                .foregroundStyle(ColorTokens.ik)

              Text(finding.severity.capitalized)
                .font(TypographyTokens.caption)
                .padding(.horizontal, SpacingTokens.small)
                .padding(.vertical, 4)
                .background(severityColor(finding.severity).opacity(0.14))
                .foregroundStyle(severityColor(finding.severity))
                .clipShape(Capsule())
            }
          }

          Divider()

          // What Was Found
          if !finding.value.isEmpty {
            VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
              Text("Detected Value")
                .font(TypographyTokens.sectionTitle)
                .foregroundStyle(ColorTokens.ik)

              Text(finding.value)
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
            Text("Details")
              .font(TypographyTokens.sectionTitle)
              .foregroundStyle(ColorTokens.ik)

            Text(finding.description)
              .font(TypographyTokens.body)
              .foregroundStyle(ColorTokens.st)
          }
        }
        .padding(SpacingTokens.large)
      }
      .background(ColorTokens.bg.ignoresSafeArea())
      .navigationTitle("Finding Detail")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .confirmationAction) {
          Button("Close") { dismiss() }
        }
      }
    }
    .presentationDetents([.medium, .large])
  }

}
