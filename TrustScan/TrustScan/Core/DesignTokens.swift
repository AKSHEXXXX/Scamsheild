import SwiftUI

// MARK: - ViewState

enum ViewState<Value> {
  case idle
  case loading(message: String?)
  case success(Value)
  case error(AppError)
  case empty
}

// MARK: - Color Tokens

enum ColorTokens {
  static let background = Color("background", bundle: nil)
  static let surface = Color("surface", bundle: nil)
  static let surfaceMuted = Color("surfaceMuted", bundle: nil)
  static let ink = Color("ink", bundle: nil)
  static let subtext = Color("subtext", bundle: nil)
  static let safe = Color("safe", bundle: nil)
  static let suspicious = Color("suspicious", bundle: nil)
  static let dangerous = Color("dangerous", bundle: nil)
  static let inconclusive = Color("inconclusive", bundle: nil)
  static let accent = Color("accent", bundle: nil)

  // Fallbacks for when asset catalog colors aren't set up
  static let backgroundFallback = Color(red: 0.95, green: 0.97, blue: 0.95)
  static let surfaceFallback = Color.white
  static let surfaceMutedFallback = Color(red: 0.90, green: 0.94, blue: 0.92)
  static let inkFallback = Color(red: 0.10, green: 0.16, blue: 0.18)
  static let subtextFallback = Color(red: 0.34, green: 0.40, blue: 0.42)
  static let safeFallback = Color(red: 0.16, green: 0.55, blue: 0.37)
  static let suspiciousFallback = Color(red: 0.86, green: 0.54, blue: 0.08)
  static let dangerousFallback = Color(red: 0.74, green: 0.20, blue: 0.18)
  static let inconclusiveFallback = Color(red: 0.38, green: 0.44, blue: 0.48)
  static let accentFallback = Color(red: 0.10, green: 0.38, blue: 0.33)
}

// Using fallbacks until asset catalog colors are added
extension ColorTokens {
  static var bg: Color { Color(red: 0.95, green: 0.97, blue: 0.95) }
  static var sf: Color { Color.white }
  static var sfm: Color { Color(red: 0.90, green: 0.94, blue: 0.92) }
  static var ik: Color { Color(red: 0.10, green: 0.16, blue: 0.18) }
  static var st: Color { Color(red: 0.34, green: 0.40, blue: 0.42) }
  static var sfe: Color { Color(red: 0.16, green: 0.55, blue: 0.37) }
  static var sus: Color { Color(red: 0.86, green: 0.54, blue: 0.08) }
  static var dng: Color { Color(red: 0.74, green: 0.20, blue: 0.18) }
  static var inc: Color { Color(red: 0.38, green: 0.44, blue: 0.48) }
  static var acc: Color { Color(red: 0.10, green: 0.38, blue: 0.33) }
}

// MARK: - Spacing Tokens

enum SpacingTokens {
  static let xSmall: CGFloat = 8
  static let small: CGFloat = 12
  static let medium: CGFloat = 16
  static let large: CGFloat = 24
  static let xLarge: CGFloat = 32
}

// MARK: - Typography Tokens

enum TypographyTokens {
  static let hero = Font.system(size: 34, weight: .bold, design: .rounded)
  static let title = Font.system(size: 24, weight: .bold, design: .rounded)
  static let sectionTitle = Font.system(size: 18, weight: .semibold, design: .rounded)
  static let body = Font.system(size: 16, weight: .regular, design: .rounded)
  static let caption = Font.system(size: 13, weight: .medium, design: .rounded)
}

// MARK: - ThreatVerdict Display Extensions

extension ThreatVerdict {
  var displayTitle: String {
    switch self {
    case .safe: return "Likely Safe"
    case .suspicious: return "Suspicious"
    case .dangerous: return "High Risk"
    case .inconclusive: return "Needs Review"
    }
  }

  var tintColor: Color {
    switch self {
    case .safe: return ColorTokens.sfe
    case .suspicious: return ColorTokens.sus
    case .dangerous: return ColorTokens.dng
    case .inconclusive: return ColorTokens.inc
    }
  }

  var iconName: String {
    switch self {
    case .safe: return "checkmark.shield.fill"
    case .suspicious: return "exclamationmark.triangle.fill"
    case .dangerous: return "xmark.shield.fill"
    case .inconclusive: return "questionmark.shield.fill"
    }
  }
}

extension IndicatorSeverity {
  var tintColor: Color {
    switch self {
    case .low: return ColorTokens.sfe
    case .medium: return ColorTokens.sus
    case .high: return ColorTokens.dng
    }
  }
}
