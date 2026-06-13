import SwiftUI

struct OnboardingView: View {
  let onFinish: () -> Void

  @State private var page = 0

  var body: some View {
    VStack(spacing: SpacingTokens.large) {
      Spacer(minLength: SpacingTokens.xLarge)

      TabView(selection: $page) {
        onboardingCard(
          title: "Scammers are getting smarter.",
          copy: "Fake invoices, phishing links, and impersonation calls cost billions every year.",
          symbol: "exclamationmark.bubble"
        )
        .tag(0)

        onboardingCard(
          title: "One scan tells you everything.",
          copy: "Upload any screenshot — message, email, invoice, or alert — and TrustScan gives you a risk verdict in seconds.",
          symbol: "shield.checkered"
        )
        .tag(1)

        onboardingCard(
          title: "Your data stays on your device.",
          copy: "Scans are analyzed privately. No data is stored on our servers without your permission.",
          symbol: "lock.shield"
        )
        .tag(2)
      }
      .tabViewStyle(.page(indexDisplayMode: .always))
      .indexViewStyle(.page(backgroundDisplayMode: .always))
      .onAppear {
        UIPageControl.appearance().currentPageIndicatorTintColor = UIColor(ColorTokens.acc)
        UIPageControl.appearance().pageIndicatorTintColor = UIColor(ColorTokens.acc).withAlphaComponent(0.3)
      }

      VStack(spacing: SpacingTokens.small) {
        Button(page == 2 ? "Get Started" : "Next") {
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
        .frame(maxWidth: .infinity, minHeight: 52)

        Button(action: { onFinish() }) {
          Text("Skip")
            .font(TypographyTokens.body)
            .foregroundStyle(ColorTokens.st)
            .frame(minWidth: 60, minHeight: 44)
        }
        .accessibilityLabel("Skip onboarding")
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
