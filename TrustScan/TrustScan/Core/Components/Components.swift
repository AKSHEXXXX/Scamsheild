import SwiftUI

func openAppSettings() {
  guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
  UIApplication.shared.open(url)
}

struct SectionCard<Content: View>: View {
  let title: String?
  @ViewBuilder let content: Content

  init(title: String? = nil, @ViewBuilder content: () -> Content) {
    self.title = title
    self.content = content()
  }

  var body: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.medium) {
      if let title {
        Text(title)
          .font(TypographyTokens.sectionTitle)
          .foregroundStyle(ColorTokens.ik)
      }
      content
    }
    .padding(SpacingTokens.large)
    .frame(maxWidth: .infinity, alignment: .leading)
    .background(
      RoundedRectangle(cornerRadius: 28, style: .continuous)
        .fill(ColorTokens.sf)
    )
  }
}

struct VerdictBadge: View {
  let verdict: ThreatVerdict

  var body: some View {
    Label(verdict.displayTitle, systemImage: verdict.iconName)
      .font(TypographyTokens.caption)
      .foregroundStyle(verdict.tintColor)
      .padding(.horizontal, SpacingTokens.small)
      .padding(.vertical, 8)
      .background(verdict.tintColor.opacity(0.14))
      .clipShape(Capsule())
      .accessibilityLabel("Threat level: \(verdict.displayTitle)")
  }
}

struct OfflineBanner: View {
  let onDismiss: () -> Void

  var body: some View {
    HStack(spacing: SpacingTokens.small) {
      Image(systemName: "wifi.slash")
        .foregroundStyle(.white)
      Text(String(localized: "HOME_OFFLINE_BANNER"))
        .font(TypographyTokens.caption)
        .foregroundStyle(.white)
      Spacer()
      Button {
        onDismiss()
      } label: {
        Image(systemName: "xmark")
          .foregroundStyle(.white.opacity(0.8))
      }
    }
    .padding(.horizontal, SpacingTokens.medium)
    .padding(.vertical, SpacingTokens.small)
    .background(Color.orange.opacity(0.9))
    .accessibilityLabel("Offline. No internet connection.")
  }
}

struct PermissionPromptSheet: View {
  let permissionType: String
  let headline: String
  let bodyText: String
  let onOpenSettings: () -> Void
  let onDismiss: () -> Void

  var body: some View {
    VStack(spacing: SpacingTokens.large) {
      Spacer()

      Image(systemName: permissionType == "camera" ? "camera.badge.ellipsis" : "photo.badge.exclamationmark")
        .font(.system(size: 60, weight: .semibold))
        .foregroundStyle(ColorTokens.acc)

      Text(headline)
        .font(TypographyTokens.title)
        .foregroundStyle(ColorTokens.ik)
        .multilineTextAlignment(.center)

      Text(bodyText)
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.st)
        .multilineTextAlignment(.center)

      VStack(spacing: SpacingTokens.small) {
        Button("Open Settings") {
          onOpenSettings()
        }
        .buttonStyle(.borderedProminent)
        .tint(ColorTokens.acc)

        Button("Not Now") {
          onDismiss()
        }
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.st)
      }

      Spacer()
    }
    .padding(SpacingTokens.large)
    .background(ColorTokens.bg.ignoresSafeArea())
  }
}

struct LoadingStateView: View {
  let message: String
  @State private var hintIndex = 0
  @Environment(\.accessibilityReduceMotion) private var reduceMotion

  private let hints = [
    "Checking for suspicious links…",
    "Scanning for scam patterns…",
    "Analyzing text content…",
    "Almost there…"
  ]

  var body: some View {
    VStack(spacing: SpacingTokens.large) {
      Spacer()

      if reduceMotion {
        Image(systemName: "shield.checkered")
          .font(.system(size: 60, weight: .semibold))
          .foregroundStyle(ColorTokens.acc)
      } else {
        ProgressView()
          .scaleEffect(1.8)
          .tint(ColorTokens.acc)
      }

      Text(message)
        .font(TypographyTokens.title)
        .foregroundStyle(ColorTokens.ik)

      Text(hints[hintIndex])
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.st)
        .animation(.easeInOut, value: hintIndex)

      Spacer()
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity)
    .background(ColorTokens.bg.ignoresSafeArea())
    .accessibilityLabel("Analyzing your image, please wait.")
    .onAppear {
      guard !reduceMotion else { return }
      Timer.scheduledTimer(withTimeInterval: 4, repeats: true) { _ in
        hintIndex = (hintIndex + 1) % hints.count
      }
    }
  }
}

struct EmptyStateView: View {
  let icon: String
  let title: String
  let description: String
  let actionTitle: String?
  let action: (() -> Void)?

  var body: some View {
    VStack(spacing: SpacingTokens.large) {
      Image(systemName: icon)
        .font(.system(size: 44))
        .foregroundStyle(ColorTokens.acc)

      Text(title)
        .font(TypographyTokens.title)
        .foregroundStyle(ColorTokens.ik)

      Text(description)
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.st)
        .multilineTextAlignment(.center)

      if let actionTitle, let action {
        Button(actionTitle) {
          action()
        }
        .buttonStyle(.borderedProminent)
        .tint(ColorTokens.acc)
      }
    }
    .padding(SpacingTokens.large)
    .frame(maxWidth: .infinity, maxHeight: .infinity)
    .background(ColorTokens.bg)
  }
}

// MARK: - Agent Degraded Warning
// Shown when the backend's primary text model (Agent 1 TF-IDF) was offline during the scan.
// Score may be lower than actual risk — on-device signals are the safety net.
struct AgentDegradedWarning: View {
  var body: some View {
    HStack(alignment: .top, spacing: SpacingTokens.small) {
      Image(systemName: "cpu.fill")
        .foregroundStyle(ColorTokens.sus)
        .font(.system(size: 14, weight: .semibold))
        .padding(.top, 1)
      Text("Server AI model was offline during this scan — the score may underestimate risk. On-device analysis has been applied as a safety net. Consider rescanning later.")
        .font(TypographyTokens.caption)
        .foregroundStyle(ColorTokens.ik)
        .fixedSize(horizontal: false, vertical: true)
    }
    .padding(SpacingTokens.medium)
    .background(
      RoundedRectangle(cornerRadius: 14, style: .continuous)
        .fill(ColorTokens.sus.opacity(0.1))
    )
    .accessibilityLabel("Server AI model was offline. This scan result may underestimate risk.")
  }
}

// MARK: - Borderline Score Warning
// Shown when the backend score is near a verdict threshold boundary.
struct BorderlineScoreWarning: View {
  let score: Int

  var body: some View {
    HStack(spacing: SpacingTokens.small) {
      Image(systemName: "exclamationmark.triangle.fill")
        .foregroundStyle(ColorTokens.sus)
        .font(.system(size: 14, weight: .semibold))
      Text("Borderline result (\(score)%) — this scan is near the detection threshold. Consider rescanning with a clearer image or additional context.")
        .font(TypographyTokens.caption)
        .foregroundStyle(ColorTokens.ik)
        .fixedSize(horizontal: false, vertical: true)
    }
    .padding(SpacingTokens.medium)
    .background(
      RoundedRectangle(cornerRadius: 14, style: .continuous)
        .fill(ColorTokens.sus.opacity(0.1))
    )
    .accessibilityLabel("Borderline result. The score of \(score) percent is near the detection threshold.")
  }
}

// MARK: - Client Override Warning
// Shown when client-side pattern matching detects scam signals the backend missed.
struct ClientOverrideWarningCard: View {
  let signals: ClientScamSignals

  var body: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.small) {
      HStack(spacing: SpacingTokens.small) {
        Image(systemName: "shield.slash.fill")
          .foregroundStyle(ColorTokens.dng)
          .font(.system(size: 16, weight: .bold))
        Text("On-device analysis flagged this message")
          .font(.system(size: 14, weight: .bold))
          .foregroundStyle(ColorTokens.dng)
      }

      Text("The server returned a low risk score, but \(signals.triggeredCount) local scam pattern\(signals.triggeredCount == 1 ? "" : "s") were detected. The analysis may be incomplete. Do not share personal information or transfer money.")
        .font(TypographyTokens.caption)
        .foregroundStyle(ColorTokens.ik)
        .fixedSize(horizontal: false, vertical: true)

      // Show which dimensions fired
      let activeLabels = activeDimensionLabels(signals)
      if !activeLabels.isEmpty {
        ScrollView(.horizontal, showsIndicators: false) {
          HStack(spacing: 6) {
            ForEach(activeLabels, id: \.self) { label in
              Text(label)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(ColorTokens.dng)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(ColorTokens.dng.opacity(0.12))
                .clipShape(Capsule())
            }
          }
        }
      }
    }
    .padding(SpacingTokens.medium)
    .background(
      RoundedRectangle(cornerRadius: 14, style: .continuous)
        .fill(ColorTokens.dng.opacity(0.08))
        .overlay(
          RoundedRectangle(cornerRadius: 14, style: .continuous)
            .stroke(ColorTokens.dng.opacity(0.25), lineWidth: 1)
        )
    )
    .accessibilityLabel("On-device analysis detected \(signals.triggeredCount) scam patterns.")
  }

  private func activeDimensionLabels(_ s: ClientScamSignals) -> [String] {
    var labels: [String] = []
    if s.policeImpersonation { labels.append("🚨 Authority Impersonation") }
    if s.urgency             { labels.append("⏰ Urgency") }
    if s.financialRequest    { labels.append("💰 Financial Request") }
    if s.otpRequest          { labels.append("🔑 OTP Request") }
    if s.threatLanguage      { labels.append("⚠️ Threat Language") }
    if s.hindiScamPatterns   { labels.append("🗣️ Regional Scam Pattern") }
    if s.homoglyphUrl        { labels.append("🔗 Spoofed Brand URL") }
    return labels
  }
}

struct InlineErrorView: View {
  let error: AppError
  let onRetry: (() -> Void)?
  let onDismiss: (() -> Void)?

  var body: some View {
    SectionCard(title: "Needs attention") {
      Text(error.errorDescription ?? "Something went wrong.")
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.ik)

      if let suggestion = error.recoverySuggestion {
        Text(suggestion)
          .font(TypographyTokens.caption)
          .foregroundStyle(ColorTokens.st)
      }

      HStack(spacing: SpacingTokens.small) {
        if error.isRetryable, let onRetry {
          Button("Try Again") { onRetry() }
            .buttonStyle(.borderedProminent)
            .tint(ColorTokens.acc)
        }
        if let onDismiss {
          Button("Dismiss") { onDismiss() }
            .buttonStyle(.bordered)
        }
      }
    }
  }
}
