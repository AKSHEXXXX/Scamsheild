import SwiftUI
import LocalAuthentication

@MainActor
final class AuthViewModel: ObservableObject {
  @Published var email = ""
  @Published var password = ""
  @Published var confirmPassword = ""
  @Published var isLoading = false
  @Published var errorMessage: String?
  @Published var isShowingSignUp = false
  @Published var signUpSuccessMessage: String?
  @Published var canUseBiometrics = false

  let authService: SupabaseAuthService

  init(authService: SupabaseAuthService) {
    self.authService = authService
    checkBiometricAvailability()
  }

  func checkBiometricAvailability() {
    let context = LAContext()
    var error: NSError?
    if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
      canUseBiometrics = true
    } else {
      canUseBiometrics = false
    }
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
        // Signed in directly
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

  func signInWithOAuth(provider: String) {
    // OAuth is handled via URL opening in the view
  }
}
