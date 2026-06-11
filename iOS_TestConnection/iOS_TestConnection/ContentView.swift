import SwiftUI

struct ContentView: View {
  private let serverIP = "192.168.1.42"
  private let port = 8000

  @State private var status = "Idle"
  @State private var isAuthenticated = false

  private var endpoint: URL {
    URL(string: "http://\(serverIP):\(port)/test")!
  }

  var body: some View {
    VStack(spacing: 24) {
      if isAuthenticated {
        VStack(spacing: 12) {
          Button("Test Connection") {
            sendMessage()
          }
          .buttonStyle(.borderedProminent)

          Text(status)
            .foregroundStyle(.secondary)

          Button("Sign Out", role: .destructive) {
            Task { try? await AuthService.signOut(); isAuthenticated = false }
          }
        }
      } else {
        VStack(spacing: 16) {
          Button("Sign in with Google") {
            Task { try? await AuthService.signInWithGoogle(); checkAuth() }
          }
          .buttonStyle(.bordered)

          Button("Sign in with Apple") {
            Task { try? await AuthService.signInWithApple(); checkAuth() }
          }
          .buttonStyle(.bordered)
        }
      }
    }
    .padding()
    .task { checkAuth() }
  }

  private func checkAuth() {
    isAuthenticated = SupabaseConfig.client.auth.session != nil
  }

  private func sendMessage() {
    status = "Sending\u{2026}"

    var request = URLRequest(url: endpoint)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.httpBody = try? JSONSerialization.data(
      withJSONObject: ["message": "Hello from iOS"]
    )

    URLSession.shared.dataTask(with: request) { _, response, error in
      DispatchQueue.main.async {
        if let error = error {
          status = "Error: \(error.localizedDescription)"
        } else if let http = response as? HTTPURLResponse, http.statusCode == 200 {
          status = "Sent \u{2705} (200 OK)"
        } else {
          status = "Unexpected response"
        }
      }
    }.resume()
  }
}
