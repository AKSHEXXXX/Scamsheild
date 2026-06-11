import Foundation
import Supabase

struct AuthService {
  static func signInWithGoogle() async throws {
    try await SupabaseConfig.client.auth.signInWithOAuth(provider: .google)
  }

  static func signInWithApple() async throws {
    try await SupabaseConfig.client.auth.signInWithOAuth(provider: .apple)
  }

  static func signOut() async throws {
    try await SupabaseConfig.client.auth.signOut()
  }
}
