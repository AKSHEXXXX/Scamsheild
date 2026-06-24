import Foundation
#if canImport(UIKit)
import UIKit
#endif

private struct RateLimitError: Decodable {
  let error: String
  let message: String
  let scans_used: Int
  let daily_cap: Int
  let resets_at: String
}

final class APIClient: @unchecked Sendable {
  private let session: URLSession
  private let baseURL: String
  private var authToken: String?

  init(baseURL: String = APIEnvironment.backendBaseURL, session: URLSession = .shared) {
    self.baseURL = baseURL
    self.session = session
  }

  func setAuthToken(_ token: String?) {
    authToken = token
  }

  func get<Response: Decodable>(path: String) async throws -> Response {
    guard let url = URL(string: "\(baseURL)\(path)") else {
      throw AppError.unexpected(message: "Invalid URL: \(path)")
    }

    var request = URLRequest(url: url)
    request.httpMethod = "GET"
    request.setValue("application/json", forHTTPHeaderField: "Accept")
    applyAuth(to: &request)

    return try await perform(request)
  }

  func post<Body: Encodable, Response: Decodable>(path: String, body: Body) async throws -> Response {
    guard let url = URL(string: "\(baseURL)\(path)") else {
      throw AppError.unexpected(message: "Invalid URL: \(path)")
    }

    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("application/json", forHTTPHeaderField: "Accept")
    
    #if canImport(UIKit)
    let deviceId = await MainActor.run { UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString }
    request.setValue(deviceId, forHTTPHeaderField: "X-Device-Id")
    #else
    request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Device-Id")
    #endif

    applyAuth(to: &request)

    let encoder = JSONEncoder()
    request.httpBody = try encoder.encode(body)

    return try await perform(request)
  }

  private func applyAuth(to request: inout URLRequest) {
    if let token = authToken {
      request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    }
  }

  private func perform<Response: Decodable>(_ request: URLRequest, attempt: Int = 1) async throws -> Response {
    let data: Data
    let response: URLResponse

    do {
      (data, response) = try await session.data(for: request)
    } catch let urlError as URLError {
      if attempt < 3 && (urlError.code == .notConnectedToInternet || urlError.code == .networkConnectionLost || urlError.code == .timedOut) {
        let delaySeconds = Int(pow(2.0, Double(attempt - 1)))
        try await Task.sleep(for: .seconds(delaySeconds))
        return try await perform(request, attempt: attempt + 1)
      }

      switch urlError.code {
      case .notConnectedToInternet, .networkConnectionLost:
        throw AppError.networkUnavailable
      case .timedOut:
        throw AppError.timeout
      default:
        throw AppError.unexpected(message: urlError.localizedDescription)
      }
    }

    guard let httpResponse = response as? HTTPURLResponse else {
      throw AppError.unexpected(message: "Invalid server response.")
    }

    let path = request.url?.path ?? "?"
    let tokenSnippet = request.value(forHTTPHeaderField: "Authorization").map { String($0.prefix(30)) } ?? "nil"
    print("[APIClient] \(request.httpMethod ?? "?") \(path) → \(httpResponse.statusCode) | auth=\(tokenSnippet)")

    switch httpResponse.statusCode {
    case 200...299:
      let decoder = JSONDecoder()
      do {
        return try decoder.decode(Response.self, from: data)
      } catch {
        print("Decoding error: \(error)")
        if let jsonString = String(data: data, encoding: .utf8) {
            print("Response JSON: \(jsonString)")
        }
        throw AppError.unexpected(message: "Unable to read the server's response.")
      }
    case 401:
      throw AppError.authenticationRequired
    case 422:
      throw AppError.unexpected(message: "The server rejected the request. Please try a different image.")
    case 429:
      let body = try? JSONDecoder().decode(RateLimitError.self, from: data)
      throw AppError.dailyLimitReached(
        message: body?.message ?? "Daily scan limit reached.",
        resetsAt: body?.resets_at ?? "midnight"
      )
    case 400...499:
      throw AppError.unexpected(message: "Request error (code \(httpResponse.statusCode)).")
    case 500...599:
      if attempt < 3 {
        let delaySeconds = Int(pow(2.0, Double(attempt - 1)))
        try await Task.sleep(for: .seconds(delaySeconds))
        return try await perform(request, attempt: attempt + 1)
      }
      throw AppError.serverError(statusCode: httpResponse.statusCode)
    default:
      throw AppError.unexpected(message: "Unexpected response (code \(httpResponse.statusCode)).")
    }
  }
}
