import SwiftUI

struct RootView: View {
  @ObservedObject var environment: AppEnvironment
  @ObservedObject var authService: SupabaseAuthService
  @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

  init(environment: AppEnvironment) {
    self.environment = environment
    self.authService = environment.authService
  }

  var body: some View {
    Group {
      if !authService.isAuthenticated {
        LoginView(viewModel: environment.authViewModel)
          .trackScreen(name: "Login")
      } else if environment.authViewModel.didJustSignUp && !hasCompletedOnboarding {
        ReferralEntryView(
          onContinue: {
            environment.authViewModel.didJustSignUp = false
          },
          onSkip: {
            environment.authViewModel.didJustSignUp = false
          },
          redeemReferral: { code in
            await environment.authService.redeemReferral(code: code)
          }
        )
        .trackScreen(name: "ReferralEntry")
      } else if !hasCompletedOnboarding {
        OnboardingView {
          hasCompletedOnboarding = true
          if let userId = authService.currentUser?.id {
            UserDefaults.standard.set(true, forKey: "hasCompletedOnboarding_\(userId)")
          }
        }
        .trackScreen(name: "Onboarding")
      } else {
        MainTabView(environment: environment, hasCompletedOnboarding: $hasCompletedOnboarding)
      }
    }
    .animation(.easeInOut(duration: 0.3), value: environment.authService.isAuthenticated)
    .animation(.easeInOut(duration: 0.3), value: hasCompletedOnboarding)
    .animation(.easeInOut(duration: 0.3), value: environment.authViewModel.didJustSignUp)
    .onChange(of: environment.authService.accessToken) { _ in
      environment.syncAuthToken()
    }
    .onChange(of: environment.authService.isAuthenticated) { isAuthenticated in
      if !isAuthenticated {
        environment.submissionViewModel.resetFlow()
      }
    }
    .alert("Enable Face ID?", isPresented: self.$environment.authViewModel.showBiometricPrompt) {
      Button("Enable", action: { environment.authViewModel.enableBiometrics() })
      Button("Not Now", role: .cancel, action: { environment.authViewModel.skipBiometrics() })
    } message: {
      Text("Would you like to enable Face ID for faster future sign-ins?")
    }
  }
}

struct MainTabView: View {
  @ObservedObject var environment: AppEnvironment
  @Binding var hasCompletedOnboarding: Bool

  @State private var selectedTab: AppTab = .scan

  var body: some View {
    TabView(selection: $selectedTab) {
      NavigationStack {
        SubmissionHomeView(viewModel: environment.submissionViewModel, historyViewModel: environment.historyViewModel)
          .trackScreen(name: "Scan")
      }
      .tabItem {
        Label("Scan", systemImage: "shield.checkered")
      }
      .tag(AppTab.scan)

      NavigationStack {
        BlogsView()
          .trackScreen(name: "Intel")
      }
      .tabItem {
        Label("Intel", systemImage: "newspaper")
      }
      .tag(AppTab.intel)

      NavigationStack {
        HistoryListView(
          viewModel: environment.historyViewModel,
          onScanRequested: { selectedTab = .scan }
        )
        .trackScreen(name: "History")
      }
      .tabItem {
        Label("History", systemImage: "clock.arrow.circlepath")
      }
      .tag(AppTab.history)

    }
    .tint(ColorTokens.acc)
    .environmentObject(environment.networkMonitor)
    .environmentObject(environment)
    .task {
      environment.submissionViewModel.resetFlow()
      await environment.submissionViewModel.loadConfiguration()
      await environment.historyViewModel.loadHistory(forceLoading: true, limit: 20)
    }
  }
}

enum AppTab: Hashable {
  case scan
  case intel
  case history
}
