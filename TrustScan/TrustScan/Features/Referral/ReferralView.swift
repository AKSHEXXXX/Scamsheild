import SwiftUI

private struct ReferralStatusDTO: Decodable {
  let referral_code: String
  let referral_link: String?
  let referrals_count: Int
  let scans_earned: Int
  let redeemed: Bool?
  let redeemed_code: String?
}

struct ScrollOffsetPreference: PreferenceKey {
  static let defaultValue: CGFloat = 0
  static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
    value = nextValue()
  }
}

enum RedeemValidationState {
  case idle
  case validating
  case valid(String)
  case invalid(String)
  case redeemed(String)

  var isValid: Bool {
    if case .valid = self { return true }
    return false
  }
}

private struct RedeemValidateResponse: Decodable {
  let valid: Bool?
}

private struct RedeemRedeemResponse: Decodable {
  let bonus_scans_credited: Int?
}

struct ReferralView: View {
  @EnvironmentObject private var environment: AppEnvironment
  @State private var isShowingShareSheet = false
  @State private var codeCopied = false
  @State private var scrollOffset: CGFloat = 0

  // Backend state — populated once GET /api/v1/referral/status is deployed
  @State private var serverCode: String? = nil
  @State private var referralsCount: Int = 0
  @State private var scansEarned: Int = 0
  @State private var isLoadingStatus = false
  @State private var hasRedeemedCode = false
  @State private var redeemedCode: String = ""
  @State private var isRedeemExpanded = false
  @State private var redeemInput = ""
  @State private var redeemState: RedeemValidationState = .idle
  @State private var showConfetti = false

  private var referralCode: String {
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

        GeometryReader { geo in
          Color.clear.preference(
            key: ScrollOffsetPreference.self,
            value: geo.frame(in: .named("scroll")).minY
          )
        }
        .frame(height: 0)

        heroCard

        referralCodeCard

        Text("Your friend must sign up using your link. 5 bonus scans are added to both accounts the moment they create a TrustScan account.")
          .font(TypographyTokens.caption)
          .foregroundStyle(ColorTokens.st)
          .multilineTextAlignment(.leading)

        howItWorksSection

        referralTrackingSection

        redeemSection

        Color.clear.frame(height: 90)
      }
      .padding(SpacingTokens.large)
    }
    .coordinateSpace(name: "scroll")
    .onPreferenceChange(ScrollOffsetPreference.self) { offset in
      scrollOffset = offset
    }
    .background(ColorTokens.bg.ignoresSafeArea())
    .navigationTitle("Invite Friends")
    .navigationBarTitleDisplayMode(.large)
    .toolbarBackground(
      scrollOffset < -100 ? .visible : .hidden,
      for: .navigationBar
    )
    .animation(.easeInOut(duration: 0.2), value: scrollOffset < -100)
    .sheet(isPresented: $isShowingShareSheet) {
      ShareSheet(items: [shareMessage])
    }
    .task {
      isLoadingStatus = true
      if let status: ReferralStatusDTO = try? await environment.apiClient.get(path: "/api/v1/referral/status") {
        serverCode = status.referral_code
        referralsCount = status.referrals_count
        scansEarned = status.scans_earned
        if status.redeemed == true, let code = status.redeemed_code {
          hasRedeemedCode = true
          redeemedCode = code
        }
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
          isLast: false,
          isComplete: true
        )
        referralStep(
          number: 2,
          title: "Your friend signs up.",
          description: "They create a TrustScan account using your invite link.",
          isLast: false,
          isComplete: referralsCount > 0
        )
        referralStep(
          number: 3,
          title: "You both get 5 free scans.",
          description: "5 bonus scans are added to both accounts automatically once they join.",
          isLast: true,
          isComplete: scansEarned > 0
        )
      }
    }
  }

  private func referralStep(number: Int, title: String, description: String, isLast: Bool, isComplete: Bool) -> some View {
    HStack(alignment: .top, spacing: SpacingTokens.medium) {
      VStack(spacing: 0) {
        ZStack {
          if isComplete {
            Circle()
              .fill(ColorTokens.acc)
              .frame(width: 40, height: 40)
            Image(systemName: "checkmark")
              .font(.system(size: 15, weight: .bold))
              .foregroundStyle(.white)
          } else {
            Circle()
              .stroke(ColorTokens.acc, lineWidth: 2)
              .frame(width: 40, height: 40)
            Text("\(number)")
              .font(.system(size: 15, weight: .bold))
              .foregroundStyle(ColorTokens.acc)
          }
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

  // MARK: - Referral Tracking

  private var referralTrackingSection: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.medium) {
      Text("Your referrals")
        .font(.system(size: 22, weight: .heavy, design: .rounded))
        .foregroundStyle(ColorTokens.ik)

      HStack(spacing: SpacingTokens.medium) {
        trackingStat(value: "\(referralsCount)", label: "Friends joined")
        trackingStat(value: "\(scansEarned)", label: "Bonus scans earned")
      }

      if referralsCount == 0 {
        Text("No referrals yet. Share your code to get started.")
          .font(TypographyTokens.body)
          .foregroundStyle(ColorTokens.st)
      } else {
        VStack(spacing: SpacingTokens.small) {
          ForEach(0..<min(referralsCount, 5), id: \.self) { _ in
            HStack(spacing: SpacingTokens.medium) {
              Circle()
                .fill(ColorTokens.acc.opacity(0.15))
                .frame(width: 40, height: 40)
                .overlay(
                  Image(systemName: "person.fill")
                    .font(.system(size: 16, weight: .medium))
                    .foregroundStyle(ColorTokens.acc)
                )
              VStack(alignment: .leading, spacing: 2) {
                Text("A friend joined")
                  .font(.system(size: 15, weight: .semibold, design: .rounded))
                  .foregroundStyle(ColorTokens.ik)
                Text(referralRelativeDate())
                  .font(TypographyTokens.caption)
                  .foregroundStyle(ColorTokens.st)
              }
              Spacer()
              Text("+5 scans")
                .font(.system(size: 14, weight: .bold, design: .rounded))
                .foregroundStyle(ColorTokens.acc)
            }
            .padding(SpacingTokens.medium)
            .background(ColorTokens.sf)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
          }
        }
      }
    }
  }

  private func trackingStat(value: String, label: String) -> some View {
    VStack(alignment: .leading, spacing: 4) {
      Text(value)
        .font(.system(size: 28, weight: .bold, design: .rounded))
        .foregroundStyle(ColorTokens.acc)
      Text(label)
        .font(TypographyTokens.caption)
        .foregroundStyle(ColorTokens.st)
    }
    .frame(maxWidth: .infinity, alignment: .leading)
    .padding(SpacingTokens.medium)
    .background(ColorTokens.sf)
    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
  }

  private func referralRelativeDate() -> String {
    "Just now"
  }

  // MARK: - Redeem Code

  private var redeemSection: some View {
    VStack(spacing: SpacingTokens.medium) {
      if hasRedeemedCode {
        HStack(spacing: SpacingTokens.small) {
          Image(systemName: "checkmark.circle.fill")
            .foregroundStyle(ColorTokens.sfe)
            .font(.system(size: 18))
          Text("You redeemed \(redeemedCode) · +5 scans added")
            .font(.system(size: 14, weight: .semibold, design: .rounded))
            .foregroundStyle(ColorTokens.ik)
          Spacer()
        }
        .padding(SpacingTokens.medium)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(ColorTokens.sfe.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
      } else {
        Button {
          withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
            isRedeemExpanded.toggle()
          }
        } label: {
          HStack {
            Image(systemName: "gift.fill")
              .foregroundStyle(ColorTokens.acc)
            Text("Redeem an invite code")
              .font(.system(size: 15, weight: .semibold, design: .rounded))
              .foregroundStyle(ColorTokens.ik)
            Spacer()
            Image(systemName: isRedeemExpanded ? "chevron.up" : "chevron.down")
              .foregroundStyle(ColorTokens.st)
          }
          .padding(SpacingTokens.medium)
        }
        .buttonStyle(.plain)

        if isRedeemExpanded {
          VStack(spacing: SpacingTokens.small) {
            HStack(spacing: 0) {
              Text("TS-")
                .font(.system(size: 16, weight: .bold, design: .monospaced))
                .foregroundStyle(ColorTokens.ik)
                .padding(.leading, SpacingTokens.medium)
              TextField("XXXXXXXX", text: $redeemInput)
                .font(.system(size: 16, weight: .bold, design: .monospaced))
                .textCase(.uppercase)
                .disableAutocorrection(true)
                .autocapitalization(.none)
                .onChange(of: redeemInput) { newVal in
                  let filtered = newVal.filter { $0.isLetter || $0.isNumber }.prefix(8)
                  if filtered != newVal { redeemInput = String(filtered) }
                  if redeemInput.count == 8 {
                    validateRedeemCode()
                  } else {
                    redeemState = .idle
                  }
                }
            }
            .padding(.vertical, 4)
            .background(ColorTokens.sfm)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

            // Validation status
            HStack(spacing: 6) {
              switch redeemState {
              case .idle:
                EmptyView()
              case .validating:
                ProgressView().tint(ColorTokens.acc)
                Text("Checking code…")
                  .font(TypographyTokens.caption)
                  .foregroundStyle(ColorTokens.st)
              case .valid:
                Image(systemName: "checkmark.circle.fill")
                  .foregroundStyle(ColorTokens.sfe)
                Text("Code applied — 5 bonus scans will be added to both accounts.")
                  .font(TypographyTokens.caption)
                  .foregroundStyle(ColorTokens.sfe)
              case .invalid(let msg):
                Image(systemName: "xmark.circle.fill")
                  .foregroundStyle(ColorTokens.dng)
                Text(msg)
                  .font(TypographyTokens.caption)
                  .foregroundStyle(ColorTokens.dng)
              case .redeemed:
                EmptyView()
              }
            }

            Button {
              Task { await redeemCode() }
            } label: {
              Text("Redeem")
                .font(.system(size: 16, weight: .bold, design: .rounded))
                .frame(maxWidth: .infinity, minHeight: 48)
            }
            .buttonStyle(.plain)
            .foregroundStyle(.white)
            .background(redeemState.isValid ? ColorTokens.acc : ColorTokens.st.opacity(0.3))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .disabled(!redeemState.isValid)
          }
          .padding(.horizontal, SpacingTokens.medium)
          .padding(.bottom, SpacingTokens.medium)
        }
      }
    }
    .background(ColorTokens.sf)
    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    .shadow(color: .black.opacity(0.04), radius: 8, y: 3)
  }

  private func validateRedeemCode() {
    redeemState = .validating
    Task {
      do {
        let response: RedeemValidateResponse = try await environment.apiClient.get(
          path: "/api/v1/referral/validate/TS-\(redeemInput)"
        )
        if response.valid == true {
          redeemState = .valid(redeemInput)
        } else {
          redeemState = .invalid("This code doesn't exist or has already been used.")
        }
      } catch {
        redeemState = .invalid("Could not validate. Check your connection.")
      }
    }
  }

  private func redeemCode() async {
    guard case .valid = redeemState else { return }
    do {
      let response: RedeemRedeemResponse = try await environment.apiClient.post(
        path: "/api/v1/referral/redeem",
        body: ["referral_code": "TS-\(redeemInput)"]
      )
      hasRedeemedCode = true
      redeemedCode = "TS-\(redeemInput)"
      redeemState = .redeemed(redeemInput)
      scansEarned += 5
      showConfetti = true
      UINotificationFeedbackGenerator().notificationOccurred(.success)
      DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
        showConfetti = false
      }
    } catch {
      redeemState = .invalid("Could not redeem. Try again later.")
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

// MARK: - Referral Entry (new signups)

struct ReferralEntryView: View {
  let onContinue: () -> Void
  let onSkip: () -> Void
  let redeemReferral: (String) async -> Void

  @State private var code = ""
  @State private var isRedeeming = false

  var body: some View {
    VStack(spacing: SpacingTokens.large) {
      Spacer()

      Image(systemName: "gift.fill")
        .font(.system(size: 56))
        .foregroundStyle(ColorTokens.acc)

      Text("Have a referral code?")
        .font(TypographyTokens.title)
        .foregroundStyle(ColorTokens.ik)

      Text("Enter a friend's referral code to get **5 free bonus scans**.")
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.st)
        .multilineTextAlignment(.center)
        .fixedSize(horizontal: false, vertical: true)

      if isRedeeming {
        ProgressView("Applying code…")
          .tint(ColorTokens.acc)
      }

      TextField("Referral code (optional)", text: $code)
        .textContentType(.oneTimeCode)
        .autocapitalization(.allCharacters)
        .disableAutocorrection(true)
        .padding()
        .background(ColorTokens.sf)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
          RoundedRectangle(cornerRadius: 16, style: .continuous)
            .stroke(ColorTokens.st.opacity(0.15), lineWidth: 1)
        )
        .padding(.horizontal, SpacingTokens.large)
        .accessibilityLabel("Referral code")
        .disabled(isRedeeming)

      HStack(spacing: SpacingTokens.medium) {
        Button(action: onSkip) {
          Text("Skip")
            .font(TypographyTokens.sectionTitle)
            .frame(maxWidth: .infinity, minHeight: 48)
        }
        .buttonStyle(.plain)
        .foregroundStyle(ColorTokens.st)
        .background(ColorTokens.sf)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(ColorTokens.st.opacity(0.3), lineWidth: 1))
        .disabled(isRedeeming)

        Button {
          let trimmed = code.trimmingCharacters(in: .whitespaces).uppercased()
          if !trimmed.isEmpty {
            isRedeeming = true
            Task {
              await redeemReferral(trimmed)
              isRedeeming = false
              onContinue()
            }
          } else {
            onContinue()
          }
        } label: {
          if isRedeeming {
            ProgressView().tint(.white).frame(maxWidth: .infinity, minHeight: 48)
          } else {
            Text("Continue")
              .font(TypographyTokens.sectionTitle)
              .frame(maxWidth: .infinity, minHeight: 48)
          }
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white)
        .background(ColorTokens.acc)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .disabled(isRedeeming)
      }
      .padding(.horizontal, SpacingTokens.large)

      Spacer()
    }
    .padding(.vertical, SpacingTokens.xLarge)
    .background(ColorTokens.bg.ignoresSafeArea())
  }
}

