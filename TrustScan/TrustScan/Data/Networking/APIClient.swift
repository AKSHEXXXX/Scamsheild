import Foundation
#if canImport(UIKit)
import UIKit
#endif

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
    let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
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

  private func perform<Response: Decodable>(_ request: URLRequest) async throws -> Response {
    let data: Data
    let response: URLResponse

    do {
      (data, response) = try await session.data(for: request)
    } catch let urlError as URLError {
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

    switch httpResponse.statusCode {
    case 200...299:
      let decoder = JSONDecoder()
      do {
        return try decoder.decode(Response.self, from: data)
      } catch {
        throw AppError.unexpected(message: "Unable to read the server's response.")
      }
    case 401:
      throw AppError.authenticationRequired
    case 422:
      throw AppError.unexpected(message: "The server rejected the request. Please try a different image.")
    case 400...499:
      throw AppError.unexpected(message: "Request error (code \(httpResponse.statusCode)).")
    case 500...599:
      throw AppError.serverError(statusCode: httpResponse.statusCode)
    default:
      throw AppError.unexpected(message: "Unexpected response (code \(httpResponse.statusCode)).")
    }
  }
}
