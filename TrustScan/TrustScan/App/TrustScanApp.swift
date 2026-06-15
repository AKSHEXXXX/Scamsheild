import SwiftUI

@main
struct TrustScanApp: App {
  @StateObject private var environment = AppEnvironment()

  var body: some Scene {
    WindowGroup {
      RootView(environment: environment)
        .onOpenURL { url in
          if url.scheme == "scamshield" && url.host == "scan" {
            // Handle Share Extension Deep Link
            if let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
               let filename = components.queryItems?.first(where: { $0.name == "file" })?.value {
               environment.submissionViewModel.handleSharedFile(filename: filename)
            }
          } else {
            // Handle Supabase Auth Callback
            Task {
              try? await environment.authService.handleOAuthCallback(url: url)
            }
          }
        }
    }
  }
}
