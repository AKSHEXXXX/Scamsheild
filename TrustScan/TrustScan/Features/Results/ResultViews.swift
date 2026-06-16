import SwiftUI

struct AnalysisResultView: View {
  let result: AnalysisResult
  let onShare: () -> Void

  @State private var selectedFinding: Finding?

  init(result: AnalysisResult, onShare: @escaping () -> Void = {}) {
    self.result = result
    self.onShare = onShare
  }

  var body: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.large) {
      // Verdict Header
      SectionCard {
        VStack(alignment: .leading, spacing: SpacingTokens.medium) {
          HStack(alignment: .center) {
            VerdictBadge(verdict: result.verdict)
            Spacer()
            Button("Share") { onShare() }
              .buttonStyle(.bordered)
          }

          if !result.summary.isEmpty {
            Text(result.summary)
              .font(TypographyTokens.body)
              .foregroundStyle(ColorTokens.ik)
          }

          Gauge(value: Double(result.score), in: 0...100) {
            Text("Risk Score")
          } currentValueLabel: {
            Text("\(result.score)%")
              .font(TypographyTokens.sectionTitle)
              .foregroundStyle(result.verdict.tintColor)
          }
          .tint(result.verdict.tintColor)
          .accessibilityLabel("Risk score: \(result.score) percent")
        }
      }

      // Flagged URLs
      if !result.flaggedUrls.isEmpty {
        SectionCard(title: "Flagged URLs") {
          VStack(alignment: .leading, spacing: SpacingTokens.small) {
            ForEach(result.flaggedUrls, id: \.self) { url in
              HStack {
                Image(systemName: "link")
                  .foregroundStyle(ColorTokens.dng)
                Text(url)
                  .font(.system(.body, design: .monospaced))
                  .foregroundStyle(ColorTokens.ik)
                  .lineLimit(1)
                  .truncationMode(.middle)
              }
              .padding(.horizontal, SpacingTokens.small)
              .padding(.vertical, SpacingTokens.xSmall)
              .background(ColorTokens.dng.opacity(0.1))
              .clipShape(Capsule())
            }
          }
        }
      }

      // Findings
      if !result.findings.isEmpty {
        SectionCard(title: "What We Found") {
          ForEach(result.findings, id: \.self) { finding in
            Button {
              selectedFinding = finding
            } label: {
              VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
                HStack {
                  Text(finding.type.capitalized.replacingOccurrences(of: "_", with: " "))
                    .font(TypographyTokens.sectionTitle)
                    .foregroundStyle(ColorTokens.ik)
                  Spacer()
                  Text(finding.severity.capitalized)
                    .font(TypographyTokens.caption)
                    .padding(.horizontal, SpacingTokens.small)
                    .padding(.vertical, 6)
                    .background(severityColor(finding.severity).opacity(0.14))
                    .foregroundStyle(severityColor(finding.severity))
                    .clipShape(Capsule())
                }

                Text(finding.description)
                  .font(TypographyTokens.body)
                  .foregroundStyle(ColorTokens.st)
                  .multilineTextAlignment(.leading)
              }
              .accessibilityLabel("\(finding.type), severity: \(finding.severity)")
            }
            .buttonStyle(.plain)

            if finding != result.findings.last {
              Divider()
            }
          }
        }
      }
    }
    .sheet(item: Binding(
      get: { selectedFinding.map { FindingIdentifiableWrapper(finding: $0) } },
      set: { selectedFinding = $0?.finding }
    )) { wrapper in
      FindingDetailSheet(finding: wrapper.finding)
    }
  }

  private func severityColor(_ severity: String) -> Color {
    switch severity.lowercased() {
    case "high": return ColorTokens.dng
    case "medium": return ColorTokens.sus
    case "low": return ColorTokens.sfe
    default: return ColorTokens.st
    }
  }
}

// Wrapper for Identifiable conformance
struct FindingIdentifiableWrapper: Identifiable {
  let id = UUID()
  let finding: Finding
}

// MARK: - Finding Detail Sheet

struct FindingDetailSheet: View {
  let finding: Finding
  @Environment(\.dismiss) private var dismiss

  var body: some View {
    NavigationStack {
      ScrollView {
        VStack(alignment: .leading, spacing: SpacingTokens.large) {
          // Header
          HStack(spacing: SpacingTokens.medium) {
            Image(systemName: "exclamationmark.triangle.fill")
              .font(.system(size: 40, weight: .semibold))
              .foregroundStyle(severityColor(finding.severity))

            VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
              Text(finding.type.capitalized.replacingOccurrences(of: "_", with: " "))
                .font(TypographyTokens.title)
                .foregroundStyle(ColorTokens.ik)

              Text(finding.severity.capitalized)
                .font(TypographyTokens.caption)
                .padding(.horizontal, SpacingTokens.small)
                .padding(.vertical, 4)
                .background(severityColor(finding.severity).opacity(0.14))
                .foregroundStyle(severityColor(finding.severity))
                .clipShape(Capsule())
            }
          }

          Divider()

          // What Was Found
          if !finding.value.isEmpty {
            VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
              Text("Detected Value")
                .font(TypographyTokens.sectionTitle)
                .foregroundStyle(ColorTokens.ik)

              Text(finding.value)
                .font(.system(.body, design: .monospaced))
                .padding(SpacingTokens.medium)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                  RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(ColorTokens.sfm)
                )
            }
          }

          // Why Suspicious
          VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
            Text("Details")
              .font(TypographyTokens.sectionTitle)
              .foregroundStyle(ColorTokens.ik)

            Text(finding.description)
              .font(TypographyTokens.body)
              .foregroundStyle(ColorTokens.st)
          }
        }
        .padding(SpacingTokens.large)
      }
      .background(ColorTokens.bg.ignoresSafeArea())
      .navigationTitle("Finding Detail")
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .confirmationAction) {
          Button("Close") { dismiss() }
        }
      }
    }
    .presentationDetents([.medium, .large])
  }

  private func severityColor(_ severity: String) -> Color {
    switch severity.lowercased() {
    case "high": return ColorTokens.dng
    case "medium": return ColorTokens.sus
    case "low": return ColorTokens.sfe
    default: return ColorTokens.st
    }
  }
}

