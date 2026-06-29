import SwiftUI

private struct ReferralStatusDTO: Decodable {
  let referral_code: String
  let referral_link: String?
  let referrals_count: Int
  let scans_earned: Int
}

struct ReferralView: View {
  @EnvironmentObject private var environment: AppEnvironment
  @State private var isShowingShareSheet = false
  @State private var codeCopied = false

  // Backend state — populated once GET /api/v1/referral/status is deployed
  @State private var serverCode: String? = nil
  @State private var referralsCount: Int = 0
  @State private var scansEarned: Int = 0
  @State private var isLoadingStatus = false

  private var referralCode: String {
    // Prefer server-generated code; fall back to deterministic client-side placeholder
    if let serverCode { return serverCode }
    let id = environment.authService.currentUser?.id ?? "GUEST000"
    return "TS-" + String(id.prefix(8)).uppercased()
  }

  private var referralLink: String {
    "https://trustscan.app/invite/\(referralCode)"
  }

  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: SpacingTokens.large) {

        heroCard

        referralCodeCard

        Text("Your friend must sign up using your link. 5 bonus scans are added to both accounts the moment they create a TrustScan account.")
          .font(TypographyTokens.caption)
          .foregroundStyle(ColorTokens.st)
          .multilineTextAlignment(.leading)

        howItWorksSection

        Spacer(minLength: SpacingTokens.large)
      }
      .padding(SpacingTokens.large)
    }
    .background(ColorTokens.bg.ignoresSafeArea())
    .navigationTitle("Invite Friends")
    .navigationBarTitleDisplayMode(.inline)
    .sheet(isPresented: $isShowingShareSheet) {
      ShareSheet(items: [shareMessage])
    }
    .task {
      // Attempt to load real referral status from backend.
      // Fails silently when endpoint is not yet deployed — client-side code shown instead.
      isLoadingStatus = true
      if let status: ReferralStatusDTO = try? await environment.apiClient.get(path: "/api/v1/referral/status") {
        serverCode = status.referral_code
        referralsCount = status.referrals_count
        scansEarned = status.scans_earned
      }
      isLoadingStatus = false
    }
  }

  // MARK: - Hero Card

  private var heroCard: some View {
    ZStack(alignment: .bottomTrailing) {
      RoundedRectangle(cornerRadius: 28, style: .continuous)
        .fill(
          LinearGradient(
            colors: [
              Color(red: 0.04, green: 0.18, blue: 0.15),
              Color(red: 0.10, green: 0.38, blue: 0.33)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
          )
        )

      Image(systemName: "person.2.fill")
        .font(.system(size: 110, weight: .black))
        .foregroundStyle(.white.opacity(0.06))
        .offset(x: 18, y: 22)

      VStack(alignment: .leading, spacing: SpacingTokens.medium) {
        VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
          Text("Give 5 scans.\nGet 5 scans.")
            .font(.system(size: 28, weight: .heavy, design: .rounded))
            .foregroundStyle(.white)
            .lineSpacing(2)

          Text("Invite a friend to TrustScan — you both get 5 free scans when they sign up.")
            .font(.system(size: 14, weight: .regular, design: .rounded))
            .foregroundStyle(.white.opacity(0.82))
            .fixedSize(horizontal: false, vertical: true)
        }

        Button {
          isShowingShareSheet = true
        } label: {
          Text("Share invite")
            .font(.system(size: 16, weight: .bold, design: .rounded))
            .foregroundStyle(Color(red: 0.04, green: 0.18, blue: 0.15))
            .frame(width: 160, height: 48)
            .background(.white)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Share your referral invite link")
      }
      .padding(SpacingTokens.xLarge)
      .frame(maxWidth: .infinity, alignment: .leading)
    }
    .frame(minHeight: 220)
    .clipped()
  }

  // MARK: - Referral Code Card

  private var referralCodeCard: some View {
    VStack(spacing: SpacingTokens.medium) {
      HStack(spacing: SpacingTokens.medium) {
        VStack(alignment: .leading, spacing: 4) {
          Text("Your invite code")
            .font(TypographyTokens.caption)
            .foregroundStyle(ColorTokens.st)
          if isLoadingStatus {
            RoundedRectangle(cornerRadius: 4)
              .fill(ColorTokens.sfm)
              .frame(width: 140, height: 24)
          } else {
            Text(referralCode)
              .font(.system(size: 20, weight: .bold, design: .monospaced))
              .foregroundStyle(ColorTokens.ik)
          }
        }

        Spacer()

        Button {
          UIPasteboard.general.string = referralLink
          withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
            codeCopied = true
          }
          DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            withAnimation { codeCopied = false }
          }
        } label: {
          HStack(spacing: 6) {
            Image(systemName: codeCopied ? "checkmark" : "doc.on.doc")
              .font(.system(size: 13, weight: .semibold))
            Text(codeCopied ? "Copied!" : "Copy")
              .font(.system(size: 14, weight: .semibold, design: .rounded))
          }
          .foregroundStyle(codeCopied ? ColorTokens.sfe : ColorTokens.acc)
          .padding(.horizontal, SpacingTokens.medium)
          .padding(.vertical, SpacingTokens.xSmall)
          .background(
            codeCopied
              ? ColorTokens.sfe.opacity(0.12)
              : ColorTokens.acc.opacity(0.10)
          )
          .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(codeCopied ? "Code copied" : "Copy your referral code")
      }

      // Stats row — visible once backend returns real data
      if referralsCount > 0 || scansEarned > 0 {
        Divider()

        HStack(spacing: 0) {
          statPill(
            value: "\(referralsCount)",
            label: referralsCount == 1 ? "friend joined" : "friends joined"
          )
          Divider().frame(height: 32)
          statPill(
            value: "\(scansEarned)",
            label: scansEarned == 1 ? "bonus scan earned" : "bonus scans earned"
          )
        }
      }
    }
    .padding(SpacingTokens.large)
    .background(
      RoundedRectangle(cornerRadius: 20, style: .continuous)
        .fill(ColorTokens.sf)
        .shadow(color: .black.opacity(0.04), radius: 8, y: 3)
    )
  }

  private func statPill(value: String, label: String) -> some View {
    VStack(spacing: 2) {
      Text(value)
        .font(.system(size: 22, weight: .bold, design: .rounded))
        .foregroundStyle(ColorTokens.acc)
      Text(label)
        .font(.system(size: 12, weight: .medium, design: .rounded))
        .foregroundStyle(ColorTokens.st)
    }
    .frame(maxWidth: .infinity)
    .accessibilityElement(children: .ignore)
    .accessibilityLabel("\(value) \(label)")
  }

  // MARK: - How It Works

  private var howItWorksSection: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.medium) {
      Text("How it works.")
        .font(.system(size: 22, weight: .heavy, design: .rounded))
        .foregroundStyle(ColorTokens.ik)

      VStack(alignment: .leading, spacing: 0) {
        referralStep(
          number: 1,
          title: "Share your invite link.",
          description: "Send your unique link to friends who haven't used TrustScan yet.",
          isLast: false
        )
        referralStep(
          number: 2,
          title: "Your friend signs up.",
          description: "They create a TrustScan account using your invite link.",
          isLast: false
        )
        referralStep(
          number: 3,
          title: "You both get 5 free scans.",
          description: "5 bonus scans are added to both accounts automatically once they join.",
          isLast: true
        )
      }
    }
  }

  private func referralStep(number: Int, title: String, description: String, isLast: Bool) -> some View {
    HStack(alignment: .top, spacing: SpacingTokens.medium) {
      VStack(spacing: 0) {
        ZStack {
          Circle()
            .fill(ColorTokens.acc.opacity(0.12))
            .frame(width: 40, height: 40)
          Image(systemName: "checkmark")
            .font(.system(size: 15, weight: .bold))
            .foregroundStyle(ColorTokens.acc)
        }

        if !isLast {
          Rectangle()
            .fill(
              LinearGradient(
                colors: [ColorTokens.acc.opacity(0.25), ColorTokens.acc.opacity(0.08)],
                startPoint: .top,
                endPoint: .bottom
              )
            )
            .frame(width: 1.5)
            .frame(maxHeight: .infinity)
            .padding(.vertical, 4)
        }
      }
      .frame(width: 40)

      VStack(alignment: .leading, spacing: 4) {
        Text("\(number). \(title)")
          .font(.system(size: 16, weight: .bold, design: .rounded))
          .foregroundStyle(ColorTokens.ik)

        Text(description)
          .font(TypographyTokens.body)
          .foregroundStyle(ColorTokens.st)
          .fixedSize(horizontal: false, vertical: true)
      }
      .padding(.bottom, isLast ? 0 : SpacingTokens.xLarge)
    }
  }

  // MARK: - Share message

  private var shareMessage: String {
    """
    Hey! I use TrustScan to protect myself from scams and suspicious messages. Sign up with my invite link and we both get 5 free scans:

    \(referralLink)

    Stay safe out there!
    """
  }
}
