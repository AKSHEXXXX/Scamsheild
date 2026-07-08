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

  let authService: SupabaseAuthService

  init(authService: SupabaseAuthService) {
    self.authService = authService
    super.init()
  }

  func authenticateWithBiometrics() async {
    let context = LAContext()
    do {
      let success = try await context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: "Authenticate to access TrustScan")
      if success {
        // If they successfully authenticate biometrically, and we had a saved token,
        // we'd log them in. Since our app auto-logs in if the token is valid,
        // this is more of a placeholder for if we implement forced biometric unlock
        // or keychain credential saving in the future.
        print("Biometric auth succeeded")
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
      } else {
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
        if self.authService.isAuthenticated, let user = self.authService.currentUser {
            AnalyticsManager.shared.identify(userId: user.id)
            AnalyticsManager.shared.reloadFeatureFlags()
            AnalyticsManager.shared.capture(event: "login", properties: ["method": provider])
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

