import SwiftUI

enum ProfileNavigation: Hashable {
  case fullHistory
  case threatsHistory
}

struct ProfileView: View {
  @EnvironmentObject private var environment: AppEnvironment
  @Environment(\.openURL) private var openURL
  @Binding var hasCompletedOnboarding: Bool

  @State private var isShowingDeleteConfirm = false
  @State private var isShowingSignOutConfirm = false
  @State private var isDeletingAccount = false
  @State private var deleteError: String?

  var body: some View {
    ScrollView {
      VStack(spacing: SpacingTokens.large) {
        
        // User Info Card
        VStack(spacing: SpacingTokens.small) {
          ZStack {
            Circle()
              .fill(ColorTokens.acc)
              .frame(width: 80, height: 80)
            
            Text(userInitials())
              .font(.system(size: 32, weight: .bold))
              .foregroundStyle(.white)
          }
          .padding(.bottom, SpacingTokens.small)
          
          Text(userEmail())
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)
          
          Button {
            if let url = URL(string: "https://trustscan.app/upgrade") {
              openURL(url)
            }
          } label: {
            HStack(spacing: 6) {
              Circle().fill(Color.green).frame(width: 8, height: 8)
              Text("Free Plan")
                .font(TypographyTokens.caption)
                .foregroundStyle(ColorTokens.st)
              Image(systemName: "chevron.right")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(ColorTokens.st.opacity(0.5))
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(ColorTokens.sf)
            .clipShape(Capsule())
          }
          .buttonStyle(.plain)
        }
        .frame(maxWidth: .infinity)
        .padding(SpacingTokens.large)
        .background(ColorTokens.sf)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        
        // Stats
        VStack(alignment: .leading, spacing: SpacingTokens.small) {
          Text("Your Stats")
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)
          
          let allEntries = environment.historyViewModel.recentEntries(limit: .max)
          let threatsCaught = allEntries.filter { $0.verdict == .scam }.count
          let totalScans = allEntries.count
          let scansLeft = max(environment.submissionViewModel.configuration.scanCreditCap - totalScans, 0)
          
          HStack(spacing: SpacingTokens.small) {
            NavigationLink(value: ProfileNavigation.fullHistory) {
              statCard(title: "Scans", value: "\(totalScans)")
            }
            .buttonStyle(.plain)
            NavigationLink(value: ProfileNavigation.threatsHistory) {
              statCard(title: "Threats caught", value: "\(threatsCaught)")
            }
            .buttonStyle(.plain)
            statCard(title: "Scans left", value: "\(scansLeft)")
              .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                  .stroke(ColorTokens.acc.opacity(0.4), lineWidth: 1)
              )
          }

          // Progress bar for free users
          let cap = environment.submissionViewModel.configuration.scanCreditCap
          if cap > 0 {
            VStack(alignment: .leading, spacing: 6) {
              ProgressView(value: Double(totalScans), total: Double(cap))
                .tint(scansLeft < 3 ? ColorTokens.dng : ColorTokens.acc)
              HStack {
                Text("\(totalScans) used")
                  .font(.system(size: 11, weight: .medium))
                  .foregroundStyle(ColorTokens.st)
                Spacer()
                Text("\(cap) free daily")
                  .font(.system(size: 11, weight: .medium))
                  .foregroundStyle(ColorTokens.st)
              }
            }
            .padding(.horizontal, 4)
          }
        }
        
        // Account Menu
        VStack(alignment: .leading, spacing: SpacingTokens.small) {
          Text("Account")
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)
          
          VStack(spacing: 0) {
            NavigationLink {
              SettingsView(
                viewModel: environment.settingsViewModel,
                hasCompletedOnboarding: $hasCompletedOnboarding,
                onHistoryChanged: {
                  Task { await environment.historyViewModel.loadHistory(forceLoading: true) }
                },
                onSignOut: {
                  environment.authService.signOut()
                }
              )
            } label: {
              menuRow(icon: "gearshape.fill", title: "Settings")
            }

            Divider().padding(.leading, 44)

            NavigationLink {
              ReferralView()
            } label: {
              menuRow(icon: "person.badge.plus", title: "Invite Friends")
            }

            Divider().padding(.leading, 44)

            NavigationLink {
              PrivacyPolicyView()
            } label: {
              menuRow(icon: "lock.fill", title: "Privacy Policy")
            }

            Divider().padding(.leading, 44)

            Button {
              if let url = URL(string: "mailto:support@trustscan.app") {
                openURL(url)
              }
            } label: {
              menuRow(icon: "questionmark.bubble.fill", title: "Help & Support")
            }
          }
          .background(ColorTokens.sf)
          .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        
        // Sign Out
        VStack(alignment: .leading, spacing: SpacingTokens.small) {
          Divider()
            .padding(.bottom, SpacingTokens.small)

          Text("Account")
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)

          Button(action: {
            isShowingSignOutConfirm = true
          }) {
            Text("Sign Out")
              .font(.system(size: 16, weight: .semibold))
              .foregroundStyle(ColorTokens.dng)
              .frame(maxWidth: .infinity, minHeight: 52)
              .background(ColorTokens.sf)
              .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
          }
          .accessibilityLabel("Sign out of your account")
        }
        .alert("Sign out of TrustScan?", isPresented: $isShowingSignOutConfirm) {
          Button("Sign Out", role: .destructive) {
            environment.authService.signOut()
          }
          Button("Cancel", role: .cancel) {}
        } message: {
          Text("You will need to sign in again to access your account.")
        }

        // Delete Account
        if let err = deleteError {
          Text(err)
            .font(TypographyTokens.caption)
            .foregroundStyle(ColorTokens.dng)
            .multilineTextAlignment(.center)
        }

        Button(action: {
          isShowingDeleteConfirm = true
        }) {
          if isDeletingAccount {
            ProgressView()
              .frame(maxWidth: .infinity, minHeight: 52)
          } else {
            Text("Delete Account")
              .font(.system(size: 15, weight: .medium))
              .foregroundStyle(ColorTokens.dng.opacity(0.7))
              .frame(maxWidth: .infinity, minHeight: 52)
          }
        }
        .disabled(isDeletingAccount)
        .accessibilityLabel("Permanently delete your account and all data")

        Color.clear.frame(height: 90)
      }
      .padding(SpacingTokens.large)
    }
    .background(ColorTokens.bg.ignoresSafeArea())
    .navigationTitle("Profile")
    .navigationDestination(for: ProfileNavigation.self) { dest in
      switch dest {
      case .fullHistory:
        HistoryListView(
          viewModel: environment.historyViewModel,
          onScanRequested: {},
          preSelectedFilter: .all
        )
      case .threatsHistory:
        HistoryListView(
          viewModel: environment.historyViewModel,
          onScanRequested: {},
          preSelectedFilter: .highRisk
        )
      }
    }
    .trackScreen(name: "Profile")
    .task {
      await environment.historyViewModel.loadHistory(forceLoading: false)
    }
    .alert("Delete Account?", isPresented: $isShowingDeleteConfirm) {
      Button("Delete Permanently", role: .destructive) {
        Task {
          isDeletingAccount = true
          deleteError = nil
          do {
            try await environment.authService.deleteAccount()
          } catch let error as AppError {
            deleteError = error.errorDescription
          } catch {
            deleteError = "Something went wrong. Please try again."
          }
          isDeletingAccount = false
        }
      }
      Button("Cancel", role: .cancel) {}
    } message: {
      Text("This permanently deletes your account and all associated data. This cannot be undone.")
    }
  }
  
  private func statCard(title: String, value: String) -> some View {
    VStack(alignment: .leading, spacing: 4) {
      Text(value)
        .font(.system(size: 28, weight: .bold, design: .rounded))
        .foregroundStyle(ColorTokens.ik)
      Text(title)
        .font(TypographyTokens.caption)
        .foregroundStyle(ColorTokens.st)
    }
    .frame(maxWidth: .infinity, alignment: .leading)
    .padding(SpacingTokens.medium)
    .background(ColorTokens.sf)
    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
  }
  
  private func menuRow(icon: String, title: String) -> some View {
    HStack(spacing: SpacingTokens.medium) {
      Image(systemName: icon)
        .font(.system(size: 18))
        .foregroundStyle(ColorTokens.acc)
        .frame(width: 24)
      
      Text(title)
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.ik)
      
      Spacer()
      
      Image(systemName: "chevron.right")
        .font(.system(size: 14, weight: .semibold))
        .foregroundStyle(ColorTokens.st.opacity(0.5))
    }
    .padding(SpacingTokens.medium)
  }
  
  private func userEmail() -> String {
    environment.authService.currentUser?.email ?? "Guest User"
  }
  
  private func userInitials() -> String {
    let email = userEmail()
    guard email != "Guest User", let firstChar = email.first else { return "G" }
    return String(firstChar).uppercased()
  }
}
