import SwiftUI

struct ProfileView: View {
  @EnvironmentObject private var environment: AppEnvironment
  @Binding var hasCompletedOnboarding: Bool
  
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
          
          HStack(spacing: 6) {
            Circle().fill(Color.green).frame(width: 8, height: 8)
            Text("Free Plan")
              .font(TypographyTokens.caption)
              .foregroundStyle(ColorTokens.st)
          }
          .padding(.horizontal, 12)
          .padding(.vertical, 6)
          .background(ColorTokens.sf)
          .clipShape(Capsule())
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
          
          HStack(spacing: SpacingTokens.medium) {
            statCard(title: "Scans", value: "\(allEntries.count)")
            statCard(title: "Threats caught", value: "\(allEntries.filter { $0.verdict == .dangerous }.count)")
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
            
            Button(action: {}) {
              menuRow(icon: "lock.fill", title: "Privacy Policy")
            }
            
            Divider().padding(.leading, 44)
            
            Button(action: {}) {
              menuRow(icon: "questionmark.bubble.fill", title: "Help & Support")
            }
          }
          .background(ColorTokens.sf)
          .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        
        // Sign Out
        Button(action: {
          environment.authService.signOut()
        }) {
          Text("Sign Out")
            .font(.system(size: 16, weight: .semibold))
            .foregroundStyle(ColorTokens.dng)
            .frame(maxWidth: .infinity, minHeight: 52)
            .background(ColorTokens.sf)
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        
      }
      .padding(SpacingTokens.large)
    }
    .background(ColorTokens.bg.ignoresSafeArea())
    .navigationTitle("Profile")
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
