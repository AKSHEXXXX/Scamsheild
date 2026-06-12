import SwiftUI

struct OnboardingView: View {
  let onFinish: () -> Void

  @State private var page = 0

  var body: some View {
    VStack(spacing: SpacingTokens.large) {
      Spacer(minLength: SpacingTokens.xLarge)

      TabView(selection: $page) {
        onboardingCard(
          title: "Scan. Detect. Stay Safer.",
          copy: "TrustScan gives you a fast second opinion when a message, invoice, or alert feels off.",
          symbol: "shield.checkered"
        )
        .tag(0)

        onboardingCard(
          title: "Start With A Screenshot",
          copy: "Pick a screenshot or capture a photo, then let the app read the text and flag common scam patterns.",
          symbol: "photo.on.rectangle.angled"
        )
        .tag(1)

        onboardingCard(
          title: "Your Privacy Matters",
          copy: "We never store your images longer than needed. Your results are private and never shared. No account required to scan.",
          symbol: "lock.shield"
        )
        .tag(2)
      }
      .tabViewStyle(.page(indexDisplayMode: .always))

      VStack(spacing: SpacingTokens.small) {
        Button(page == 2 ? "Start Scanning" : "Next") {
          if page < 2 {
            withAnimation(.easeInOut) {
              page += 1
            }
          } else {
            onFinish()
          }
        }
        .buttonStyle(.borderedProminent)
        .tint(ColorTokens.acc)

        Button("Skip") {
          onFinish()
        }
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.st)
      }

      Spacer(minLength: SpacingTokens.large)
    }
    .padding(.horizontal, SpacingTokens.large)
    .background(
      LinearGradient(
        colors: [ColorTokens.bg, .white],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
      )
      .ignoresSafeArea()
    )
  }

  private func onboardingCard(title: String, copy: String, symbol: String) -> some View {
    VStack(alignment: .leading, spacing: SpacingTokens.medium) {
      Image(systemName: symbol)
        .font(.system(size: 60, weight: .semibold))
        .foregroundStyle(ColorTokens.acc)
        .frame(maxWidth: .infinity, alignment: .leading)

      Text(title)
        .font(TypographyTokens.hero)
        .foregroundStyle(ColorTokens.ik)

      Text(copy)
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.st)

      Spacer()
    }
    .padding(SpacingTokens.large)
    .frame(maxWidth: .infinity, maxHeight: 420, alignment: .topLeading)
    .background(
      RoundedRectangle(cornerRadius: 28, style: .continuous)
        .fill(ColorTokens.sf)
        .shadow(color: Color.black.opacity(0.06), radius: 18, y: 12)
    )
  }
}
