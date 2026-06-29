import SwiftUI
import UIKit

@main
@MainActor
struct TrustScanApp: App {
  @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
  @StateObject private var environment = AppEnvironment()

  var body: some Scene {
    WindowGroup {
      RootView(environment: environment)
        .onOpenURL { url in
          guard url.scheme == "scamshield" else { return }

          switch url.host {
          case "scan":
            // Share Extension deep links
            if let components = URLComponents(url: url, resolvingAgainstBaseURL: false) {
              if let filename = components.queryItems?.first(where: { $0.name == "file" })?.value {
                environment.submissionViewModel.handleSharedFile(filename: filename)
              } else if let text = components.queryItems?.first(where: { $0.name == "text" })?.value {
                environment.submissionViewModel.handleSharedText(text)
              } else if let sharedUrl = components.queryItems?.first(where: { $0.name == "url" })?.value {
                environment.submissionViewModel.handleSharedText(sharedUrl)
              }
            }

          case "invite":
            // Referral invite links: scamshield://invite/CODE or scamshield://invite?ref=CODE
            let components = URLComponents(url: url, resolvingAgainstBaseURL: false)
            let code = components?.queryItems?.first(where: { $0.name == "ref" })?.value
                    ?? url.pathComponents.dropFirst().first
            if let code, !code.isEmpty {
              UserDefaults.standard.set(code, forKey: "pendingReferralCode")
            }

          default:
            // Supabase OAuth callback
            Task {
              try? await environment.authService.handleOAuthCallback(url: url)
            }
          }
        }
    }
  }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
  private var protectionWindow: UIWindow?

  func applicationDidBecomeActive(_ application: UIApplication) {
    NotificationCenter.default.addObserver(
      self,
      selector: #selector(screenCaptureChanged),
      name: UIScreen.capturedDidChangeNotification,
      object: nil
    )
    updateProtection()
  }

  @objc private func screenCaptureChanged() {
    updateProtection()
  }

  private func updateProtection() {
    if UIScreen.main.isCaptured {
      showOverlay()
    } else {
      hideOverlay()
    }
  }

  private func showOverlay() {
    guard protectionWindow == nil else { return }
    guard let windowScene = UIApplication.shared.connectedScenes
      .first(where: { $0.activationState == .foregroundActive }) as? UIWindowScene
    else { return }
    let w = UIWindow(windowScene: windowScene)
    w.windowLevel = .alert + 1
    w.backgroundColor = .black
    let lbl = UILabel(frame: w.bounds)
    lbl.text = "Content hidden during screen recording"
    lbl.textColor = .white
    lbl.textAlignment = .center
    w.addSubview(lbl)
    w.isHidden = false
    protectionWindow = w
  }

  private func hideOverlay() {
    protectionWindow?.isHidden = true
    protectionWindow = nil
  }
}
