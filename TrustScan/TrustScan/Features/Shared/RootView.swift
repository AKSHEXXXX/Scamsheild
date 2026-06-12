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
      } else if !hasCompletedOnboarding {
        OnboardingView {
          hasCompletedOnboarding = true
        }
      } else {
        MainTabView(environment: environment, hasCompletedOnboarding: $hasCompletedOnboarding)
      }
    }
    .animation(.easeInOut(duration: 0.3), value: environment.authService.isAuthenticated)
    .animation(.easeInOut(duration: 0.3), value: hasCompletedOnboarding)
    .onChange(of: environment.authService.accessToken) { _ in
      environment.syncAuthToken()
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
        SubmissionHomeView(viewModel: environment.submissionViewModel)
      }
      .tabItem {
        Label("Scan", systemImage: "shield.checkered")
      }
      .tag(AppTab.scan)

      NavigationStack {
        HistoryListView(
          viewModel: environment.historyViewModel,
          onScanRequested: { selectedTab = .scan }
        )
      }
      .tabItem {
        Label("History", systemImage: "clock.arrow.circlepath")
      }
      .tag(AppTab.history)

      NavigationStack {
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
      }
      .tabItem {
        Label("Settings", systemImage: "gearshape")
      }
      .tag(AppTab.settings)
    }
    .tint(ColorTokens.acc)
    .environmentObject(environment.networkMonitor)
    .environmentObject(environment)
    .task {
      await environment.submissionViewModel.loadConfiguration()
      await environment.historyViewModel.loadHistory(forceLoading: true)
    }
  }
}

enum AppTab: Hashable {
  case scan
  case history
  case settings
}
