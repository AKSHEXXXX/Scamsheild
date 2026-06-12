import Foundation

enum AppError: Error, LocalizedError, Hashable, Identifiable {
  case invalidImage
  case imageTooLarge(maxMegabytes: Int)
  case analysisUnavailable
  case noScamSignalsDetected
  case noTextDetected
  case persistenceFailure
  case permissionDenied(resource: String)
  case networkUnavailable
  case serverError(statusCode: Int)
  case timeout
  case authenticationRequired
  case authenticationFailed(message: String)
  case unexpected(message: String)

  var id: String { localizedDescription }

  var errorDescription: String? {
    switch self {
    case .invalidImage:
      return "This image could not be processed."
    case let .imageTooLarge(maxMegabytes):
      return "Choose an image smaller than \(maxMegabytes) MB."
    case .analysisUnavailable:
      return "The scanner is not available right now."
    case .noScamSignalsDetected:
      return "No clear scam signals were found in this screenshot."
    case .noTextDetected:
      return "We couldn't read enough text from this image."
    case .persistenceFailure:
      return "The result was analyzed, but local saving failed."
    case let .permissionDenied(resource):
      return "\(resource) permission is denied."
    case .networkUnavailable:
      return "No internet connection. Please check your connection and try again."
    case let .serverError(statusCode):
      return "Something went wrong on our end (code \(statusCode)). Please try again later."
    case .timeout:
      return "Analysis is taking longer than expected. Please try again."
    case .authenticationRequired:
      return "Please sign in to continue."
    case let .authenticationFailed(message):
      return message
    case let .unexpected(message):
      return message
    }
  }

  var recoverySuggestion: String? {
    switch self {
    case .invalidImage:
      return "Try another screenshot or retake the photo in better lighting."
    case .imageTooLarge:
      return "Capture a tighter crop or choose a smaller image."
    case .analysisUnavailable:
      return "Wait a moment and retry."
    case .noScamSignalsDetected:
      return "Review the message manually and rescan a clearer screenshot if needed."
    case .noTextDetected:
      return "Use a clearer screenshot with larger text."
    case .persistenceFailure:
      return "You can still review the result, but it will not appear in history."
    case .permissionDenied:
      return "Open Settings and allow access, then come back and try again."
    case .networkUnavailable:
      return "Check your Wi-Fi or cellular connection and try again."
    case .serverError:
      return "Our servers are having trouble. Please wait a moment and retry."
    case .timeout:
      return "Retry once. If it keeps happening, check your connection."
    case .authenticationRequired:
      return "Sign in with your email or social account to use TrustScan."
    case .authenticationFailed:
      return "Check your credentials and try again."
    case .unexpected:
      return "Retry once. If it keeps happening, restart the app."
    }
  }

  var isRetryable: Bool {
    switch self {
    case .networkUnavailable, .serverError, .timeout, .analysisUnavailable:
      return true
    default:
      return false
    }
  }
}
