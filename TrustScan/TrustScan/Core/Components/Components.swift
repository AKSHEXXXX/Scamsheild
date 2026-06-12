import SwiftUI

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
      Text("No internet connection — scanning is unavailable.")
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
