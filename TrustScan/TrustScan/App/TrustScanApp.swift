import SwiftUI

@main
struct TrustScanApp: App {
  @StateObject private var environment = AppEnvironment()

  var body: some Scene {
    WindowGroup {
      RootView(environment: environment)
        .onOpenURL { url in
          Task {
            try? await environment.authService.handleOAuthCallback(url: url)
          }
        }
    }
  }
}
