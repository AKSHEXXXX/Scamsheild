import SwiftUI

/// A standalone, attention-grabbing counter showing the rupee total lost to
/// scams in India "today". On appear it animates a one-shot count-up from ₹0 to
/// the amount lost so far today (a snapshot at the moment the poster opens),
/// then settles and holds — it does NOT keep ticking.
///
/// The per-second rate is derived from India's reported cyber-fraud losses:
/// ≈ ₹11,000+ crore in FY2024 (Indian Cybercrime Coordination Centre / I4C)
/// ÷ 525,600 minutes/year ≈ ₹2 lakh per minute ≈ ₹3,333 per second.
///
/// Respects Reduce Motion: when enabled, shows the figure immediately with no
/// count-up animation.
struct ScamLossCounterView: View {
  /// ≈ ₹2 lakh/min — derived from I4C FY2024 cyber-fraud losses (see doc comment).
  private let lossPerSecond: Double = 3_333

  /// How long the one-shot count-up animation runs.
  private let countUpDuration: TimeInterval = 2.5

  /// Frame cadence for the count-up (~60fps).
  private let frameInterval: TimeInterval = 0.016

  @Environment(\.accessibilityReduceMotion) private var reduceMotion

  @State private var displayedAmount: Double = 0
  @State private var timer: Timer?

  var body: some View {
    VStack(spacing: SpacingTokens.medium) {
      ZStack {
        Circle()
          .fill(ColorTokens.dng.opacity(0.10))
          .frame(width: 76, height: 76)
        Image(systemName: "exclamationmark.triangle.fill")
          .font(.system(size: 36, weight: .semibold))
          .foregroundStyle(ColorTokens.dng)
      }

      Text("Lost to scams in India today")
        .font(TypographyTokens.caption)
        .foregroundStyle(ColorTokens.st)

      Text(formatted(displayedAmount))
        .font(.system(size: 44, weight: .bold, design: .rounded))
        .foregroundStyle(ColorTokens.dng)
        .monospacedDigit()
        .lineLimit(1)
        .minimumScaleFactor(0.5)

      Text("≈ ₹2 lakh every minute · Source: I4C, 2024")
        .font(TypographyTokens.caption)
        .foregroundStyle(ColorTokens.st)
        .multilineTextAlignment(.center)
    }
    .frame(maxWidth: .infinity)
    .accessibilityElement(children: .ignore)
    .accessibilityLabel("Approximately 2 lakh rupees are lost to scams every minute in India.")
    .onAppear(perform: start)
    .onDisappear(perform: stop)
  }

  // MARK: - Lifecycle

  private func start() {
    let baseline = secondsSinceMidnight() * lossPerSecond

    guard !reduceMotion else {
      // Calm path: show the figure outright, no count-up.
      displayedAmount = baseline
      return
    }

    // One-shot eased count-up from 0 → baseline, then stop.
    displayedAmount = 0
    timer?.invalidate()
    let startTime = Date()
    let t = Timer.scheduledTimer(withTimeInterval: frameInterval, repeats: true) { _ in
      Task { @MainActor in
        let elapsed = Date().timeIntervalSince(startTime)
        let progress = min(1, elapsed / countUpDuration)
        let eased = 1 - pow(1 - progress, 3) // ease-out cubic
        displayedAmount = baseline * eased
        if progress >= 1 {
          displayedAmount = baseline
          stop()
        }
      }
    }
    RunLoop.main.add(t, forMode: .common) // keep animating during TabView paging
    timer = t
  }

  private func stop() {
    timer?.invalidate()
    timer = nil
  }

  // MARK: - Helpers

  private func secondsSinceMidnight() -> Double {
    let now = Date()
    let startOfDay = Calendar.current.startOfDay(for: now)
    return max(0, now.timeIntervalSince(startOfDay))
  }

  private static let formatter: NumberFormatter = {
    let f = NumberFormatter()
    f.numberStyle = .decimal
    f.locale = Locale(identifier: "en_IN") // Indian grouping (lakh / crore)
    f.maximumFractionDigits = 0
    return f
  }()

  private func formatted(_ amount: Double) -> String {
    let number = NSNumber(value: amount.rounded())
    let grouped = Self.formatter.string(from: number) ?? "\(Int(amount))"
    return "₹\(grouped)"
  }
}

#Preview {
  ScamLossCounterView()
    .padding()
    .background(Color.white)
}
