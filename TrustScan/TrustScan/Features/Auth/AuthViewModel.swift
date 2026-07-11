import SwiftUI
import LocalAuthentication
import AuthenticationServices

@MainActor
final class AuthViewModel: NSObject, ObservableObject {
  @Published var email = ""
  @Published var password = ""
  @Published var confirmPassword = ""
  @Published var isLoading = false
  @Published var errorMessage: String?
  @Published var isShowingSignUp = false
  @Published var signUpSuccessMessage: String?
  @Published var showBiometricPrompt = false
  @Published var hasBiometricsEnabled: Bool
  @Published var didJustSignUp = false

  let authService: SupabaseAuthService

  init(authService: SupabaseAuthService) {
    self.authService = authService
    self.hasBiometricsEnabled = UserDefaults.standard.bool(forKey: "biometricsEnabled")
    super.init()
  }

  private func promptBiometricsIfAvailable() {
    let context = LAContext()
    guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil) else { return }
    showBiometricPrompt = true
  }

  func enableBiometrics() {
    hasBiometricsEnabled = true
    UserDefaults.standard.set(true, forKey: "biometricsEnabled")
    showBiometricPrompt = false
  }

  func skipBiometrics() {
    showBiometricPrompt = false
  }

  func authenticateWithBiometrics() async {
    let context = LAContext()
    do {
      let success = try await context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: "Authenticate to access TrustScan")
      if success, authService.isAuthenticated {
        return
      } else if success {
        try? await authService.refreshAccessToken()
      }
    } catch {
      errorMessage = "Biometric authentication failed."
    }
  }

  func signIn() async {
    guard !email.isEmpty, !password.isEmpty else {
      errorMessage = "Please enter your email and password."
      return
    }
    isLoading = true
    errorMessage = nil

    do {
      try await authService.signIn(email: email, password: password)
      
      if let user = authService.currentUser {
          AnalyticsManager.shared.identify(userId: user.id)
          AnalyticsManager.shared.reloadFeatureFlags()
          AnalyticsManager.shared.capture(event: "login", properties: ["method": "password"])
      }
      
      // Existing users can't redeem a referral — clear any stale pending code
      UserDefaults.standard.removeObject(forKey: "pendingReferralCode")

      if !hasBiometricsEnabled {
        promptBiometricsIfAvailable()
      }
    } catch let error as AppError {
      errorMessage = error.errorDescription
    } catch {
      errorMessage = error.localizedDescription
    }

    isLoading = false
  }

  func signUp() async {
    guard !email.isEmpty, !password.isEmpty else {
      errorMessage = "Please fill in all fields."
      return
    }
    guard password == confirmPassword else {
      errorMessage = "Passwords do not match."
      return
    }
    guard password.count >= 6 else {
      errorMessage = "Password must be at least 6 characters."
      return
    }

    isLoading = true
    errorMessage = nil

    do {
      try await authService.signUp(email: email, password: password)
      if authService.isAuthenticated {
        didJustSignUp = true
        if let user = authService.currentUser {
            AnalyticsManager.shared.identify(userId: user.id)
            AnalyticsManager.shared.reloadFeatureFlags()
            AnalyticsManager.shared.capture(event: "signup", properties: ["method": "password"])
        }
          
        // Redeem any pending referral code from an invite link
        let pending = UserDefaults.standard.string(forKey: "pendingReferralCode") ?? ""
        if !pending.isEmpty {
          Task {
            await authService.redeemReferral(code: pending)
            UserDefaults.standard.removeObject(forKey: "pendingReferralCode")
          }
        }

        if !hasBiometricsEnabled {
          promptBiometricsIfAvailable()
        }
      } else {
        didJustSignUp = true
        signUpSuccessMessage = "Check your email to confirm your account, then sign in."
        isShowingSignUp = false
      }
    } catch let error as AppError {
      errorMessage = error.errorDescription
    } catch {
      errorMessage = error.localizedDescription
    }

    isLoading = false
  }

  func resetPassword() async {
    guard !email.isEmpty else {
      errorMessage = "Enter your email address first, then tap Forgot Password."
      return
    }
    isLoading = true
    errorMessage = nil
    do {
      try await authService.resetPassword(email: email)
      signUpSuccessMessage = "Password reset email sent — check your inbox."
    } catch let error as AppError {
      errorMessage = error.errorDescription
    } catch {
      errorMessage = "Failed to send reset email. Please try again."
    }
    isLoading = false
  }

  func signInWithOAuth(provider: String) {
    guard let url = authService.oAuthURL(provider: provider) else { return }

    let session = ASWebAuthenticationSession(
      url: url,
      callbackURLScheme: "scamshield"
    ) { callbackURL, error in
      guard error == nil, let callbackURL = callbackURL else {
        return
      }
      Task {
        try? await self.authService.handleOAuthCallback(url: callbackURL)
        if self.authService.isAuthenticated {
            if let user = self.authService.currentUser {
                AnalyticsManager.shared.identify(userId: user.id)
                AnalyticsManager.shared.reloadFeatureFlags()
                AnalyticsManager.shared.capture(event: "login", properties: ["method": provider])
            }
            let pending = UserDefaults.standard.string(forKey: "pendingReferralCode") ?? ""
            if !pending.isEmpty {
                Task {
                    await self.authService.redeemReferral(code: pending)
                    UserDefaults.standard.removeObject(forKey: "pendingReferralCode")
                }
            }
            if !self.hasBiometricsEnabled {
              self.promptBiometricsIfAvailable()
            }
        }
      }
    }
    
    session.presentationContextProvider = self
    // This forces Google to not use the previous login session
    session.prefersEphemeralWebBrowserSession = true
    session.start()
  }
}

extension AuthViewModel: @preconcurrency ASWebAuthenticationPresentationContextProviding {
  nonisolated func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
    return ASPresentationAnchor()
  }
}

