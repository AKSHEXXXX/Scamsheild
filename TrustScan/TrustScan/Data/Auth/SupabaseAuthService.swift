import Foundation

@MainActor
final class SupabaseAuthService: ObservableObject {
  @Published var currentUser: SupabaseUser?
  @Published var accessToken: String?
  @Published var isAuthenticated = false

  private let supabaseURL: String
  private let anonKey: String
  private let session: URLSession

  private let tokenKey = "supabase_access_token"
  private let refreshTokenKey = "supabase_refresh_token"

  init(
    supabaseURL: String = APIEnvironment.supabaseURL,
    anonKey: String = APIEnvironment.supabaseAnonKey,
    session: URLSession = .shared
  ) {
    self.supabaseURL = supabaseURL
    self.anonKey = anonKey
    self.session = session

    if let storedToken = UserDefaults.standard.string(forKey: tokenKey) {
      self.accessToken = storedToken
      self.isAuthenticated = true
      Task { await fetchUser() }
    }
  }

  // MARK: - Sign Up

  func signUp(email: String, password: String) async throws {
    let url = URL(string: "\(supabaseURL)/auth/v1/signup")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue(anonKey, forHTTPHeaderField: "apikey")

    let body = SupabaseSignUpRequest(email: email, password: password)
    request.httpBody = try JSONEncoder().encode(body)

    let (data, response) = try await session.data(for: request)

    guard let httpResponse = response as? HTTPURLResponse else {
      throw AppError.unexpected(message: "Invalid response from auth server.")
    }

    if httpResponse.statusCode == 200 || httpResponse.statusCode == 201 {
      let authResponse = try JSONDecoder().decode(SupabaseAuthResponse.self, from: data)
      if let token = authResponse.access_token {
        persistTokens(access: token, refresh: authResponse.refresh_token)
        self.currentUser = authResponse.user
        return
      }
      // Email confirmation required — account created but no token
      return
    }

    let errorResponse = try? JSONDecoder().decode(SupabaseAuthResponse.self, from: data)
    let message = errorResponse?.error_description ?? errorResponse?.msg ?? "Sign up failed."
    throw AppError.authenticationFailed(message: message)
  }

  // MARK: - Sign In

  func signIn(email: String, password: String) async throws {
    try await signInWithSupabase(email: email, password: password)
  }

  private func signInWithSupabase(email: String, password: String) async throws {
    let url = URL(string: "\(supabaseURL)/auth/v1/token?grant_type=password")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue(anonKey, forHTTPHeaderField: "apikey")

    let body = SupabaseSignInRequest(email: email, password: password)
    request.httpBody = try JSONEncoder().encode(body)

    let (data, response) = try await session.data(for: request)

    guard let httpResponse = response as? HTTPURLResponse else {
      throw AppError.unexpected(message: "Invalid response from auth server.")
    }

    if httpResponse.statusCode == 200 {
      let authResponse = try JSONDecoder().decode(SupabaseAuthResponse.self, from: data)
      guard let token = authResponse.access_token else {
        throw AppError.authenticationFailed(message: "No access token received.")
      }
      persistTokens(access: token, refresh: authResponse.refresh_token)
      self.currentUser = authResponse.user
      return
    }

    let errorResponse = try? JSONDecoder().decode(SupabaseAuthResponse.self, from: data)
    let message = errorResponse?.error_description ?? errorResponse?.msg ?? "Invalid credentials."
    throw AppError.authenticationFailed(message: message)
  }

  // MARK: - OAuth (Apple / Google)

  func oAuthURL(provider: String) -> URL? {
    let redirectScheme = "trustscan"
    let redirectURL = "\(redirectScheme)://auth-callback"
    let urlString = "\(supabaseURL)/auth/v1/authorize?provider=\(provider)&redirect_to=\(redirectURL)"
    return URL(string: urlString)
  }

  func handleOAuthCallback(url: URL) async throws {
    // Parse the fragment or query for access_token
    guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return }

    // Supabase returns tokens in the URL fragment
    let fragment = url.fragment ?? ""
    let params = fragment.split(separator: "&").reduce(into: [String: String]()) { result, pair in
      let parts = pair.split(separator: "=", maxSplits: 1)
      if parts.count == 2 {
        result[String(parts[0])] = String(parts[1])
      }
    }

    if let token = params["access_token"] {
      let refreshToken = params["refresh_token"]
      persistTokens(access: token, refresh: refreshToken)
      await fetchUser()
      return
    }

    // Also check query params
    if let token = components.queryItems?.first(where: { $0.name == "access_token" })?.value {
      let refreshToken = components.queryItems?.first(where: { $0.name == "refresh_token" })?.value
      persistTokens(access: token, refresh: refreshToken)
      await fetchUser()
      return
    }

    throw AppError.authenticationFailed(message: "OAuth sign-in did not return a valid token.")
  }

  // MARK: - Sign Out

  func signOut() {
    UserDefaults.standard.removeObject(forKey: tokenKey)
    UserDefaults.standard.removeObject(forKey: refreshTokenKey)
    accessToken = nil
    currentUser = nil
    isAuthenticated = false
  }

  // MARK: - Fetch User

  func fetchUser() async {
    guard let token = accessToken else { return }

    let url = URL(string: "\(supabaseURL)/auth/v1/user")!
    var request = URLRequest(url: url)
    request.httpMethod = "GET"
    request.setValue(anonKey, forHTTPHeaderField: "apikey")
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

    do {
      let (data, response) = try await session.data(for: request)
      guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
        signOut()
        return
      }
      currentUser = try JSONDecoder().decode(SupabaseUser.self, from: data)
    } catch {
      // Token may be expired
      signOut()
    }
  }

  // MARK: - Private

  private func persistTokens(access: String, refresh: String?) {
    accessToken = access
    isAuthenticated = true
    UserDefaults.standard.set(access, forKey: tokenKey)
    if let refresh {
      UserDefaults.standard.set(refresh, forKey: refreshTokenKey)
    }
  }
}
