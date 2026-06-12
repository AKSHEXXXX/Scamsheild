import Foundation

enum APIEnvironment {
  private static let env: [String: String] = {
    guard let path = Bundle.main.path(forResource: ".env", ofType: nil),
          let contents = try? String(contentsOfFile: path) else {
      print("WARNING: .env file not found. Falling back to defaults.")
      return [:]
    }
    
    var dict = [String: String]()
    let lines = contents.components(separatedBy: .newlines)
    for line in lines {
      let trimmed = line.trimmingCharacters(in: .whitespaces)
      if trimmed.isEmpty || trimmed.hasPrefix("#") { continue }
      let parts = trimmed.split(separator: "=", maxSplits: 1).map(String.init)
      if parts.count == 2 {
        dict[parts[0]] = parts[1]
      }
    }
    return dict
  }()

  static var supabaseURL: String {
    env["SUPABASE_URL"] ?? "https://placeholder.supabase.co"
  }
  
  static var supabaseAnonKey: String {
    env["SUPABASE_ANON_KEY"] ?? "placeholder_anon_key"
  }
  
  static var backendBaseURL: String {
    env["BACKEND_URL"] ?? "https://placeholder-backend.com"
  }

  // Hardwired admin credentials
  static let adminEmail = "admin@trustscan.app"
  static let adminPassword = "Admin123!"
}
