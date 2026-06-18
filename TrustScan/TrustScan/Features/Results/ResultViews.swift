import SwiftUI

private func severityColor(_ severity: String) -> Color {
  switch severity.lowercased() {
  case "high": return ColorTokens.dng
  case "medium": return ColorTokens.sus
  case "low": return ColorTokens.sfe
  default: return ColorTokens.st
  }
}

struct AnalysisResultView: View {
  let result: AnalysisResult
  let onShare: () -> Void

  @State private var selectedFinding: Finding?

  init(result: AnalysisResult, onShare: @escaping () -> Void = {}) {
    self.result = result
    self.onShare = onShare
  }

  @State private var animatedScore: Double = 0
  
  var body: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.large) {
      // Premium Score Header
      VStack(spacing: SpacingTokens.large) {
        HStack {
          VerdictBadge(verdict: result.verdict)
          Spacer()
          Button {
            onShare()
          } label: {
            Image(systemName: "square.and.arrow.up")
              .font(.system(size: 16, weight: .semibold))
              .foregroundStyle(.white)
              .padding(.horizontal, 16)
              .padding(.vertical, 8)
              .background(ColorTokens.acc)
              .clipShape(Capsule())
              .shadow(color: ColorTokens.acc.opacity(0.3), radius: 8, x: 0, y: 4)
          }
        }
        
        // Circular Gauge
        ZStack {
          Circle()
            .stroke(Color.gray.opacity(0.15), lineWidth: 16)
          
          Circle()
            .trim(from: 0, to: CGFloat(animatedScore) / 100.0)
            .stroke(
              AngularGradient(
                gradient: Gradient(colors: [result.verdict.tintColor.opacity(0.5), result.verdict.tintColor]),
                center: .center,
                startAngle: .degrees(-90),
                endAngle: .degrees(270)
              ),
              style: StrokeStyle(lineWidth: 16, lineCap: .round)
            )
            .rotationEffect(.degrees(-90))
            .shadow(color: result.verdict.tintColor.opacity(0.4), radius: 10, x: 0, y: 0)
          
          VStack(spacing: 4) {
            Text("Risk Score")
              .font(TypographyTokens.caption)
              .foregroundStyle(ColorTokens.st)
              .textCase(.uppercase)
            
            Text("\(Int(animatedScore))%")
              .font(.system(size: 48, weight: .bold, design: .rounded))
              .foregroundStyle(result.verdict.tintColor)
              .contentTransition(.numericText())
          }
        }
        .frame(width: 180, height: 180)
        .padding(.vertical, SpacingTokens.medium)
        
        if !result.summary.isEmpty {
          Text(result.summary)
            .font(TypographyTokens.body)
            .foregroundStyle(ColorTokens.ik)
            .multilineTextAlignment(.center)
            .padding(.horizontal)
        }
      }
      .padding(SpacingTokens.large)
      .background(
        RoundedRectangle(cornerRadius: 24, style: .continuous)
          .fill(ColorTokens.sfm)
          .shadow(color: Color.black.opacity(0.04), radius: 12, x: 0, y: 6)
      )
      
      // Flagged URLs
      if !result.flaggedUrls.isEmpty {
        VStack(alignment: .leading, spacing: SpacingTokens.medium) {
          Text("Flagged Links")
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)
            .padding(.horizontal, 4)
          
          ForEach(result.flaggedUrls, id: \.self) { url in
            HStack(spacing: 12) {
              ZStack {
                Circle()
                  .fill(ColorTokens.dng.opacity(0.15))
                  .frame(width: 36, height: 36)
                Image(systemName: "link.badge.plus")
                  .foregroundStyle(ColorTokens.dng)
                  .font(.system(size: 14, weight: .bold))
              }
              
              Text(url)
                .font(.system(.subheadline, design: .monospaced))
                .foregroundStyle(ColorTokens.ik)
                .lineLimit(1)
                .truncationMode(.middle)
              
              Spacer()
            }
            .padding(12)
            .background(
              RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(ColorTokens.sf)
                .shadow(color: Color.black.opacity(0.03), radius: 6, x: 0, y: 2)
            )
          }
        }
      }

      // Findings
      if !result.findings.isEmpty {
        VStack(alignment: .leading, spacing: SpacingTokens.medium) {
          Text("Threat Indicators")
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)
            .padding(.horizontal, 4)
          
          VStack(spacing: SpacingTokens.small) {
            ForEach(result.findings, id: \.self) { finding in
              Button {
                selectedFinding = finding
              } label: {
                HStack(alignment: .top, spacing: SpacingTokens.medium) {
                  Image(systemName: "exclamationmark.shield.fill")
                    .font(.system(size: 24))
                    .foregroundStyle(severityColor(finding.severity))
                    .padding(.top, 2)
                  
                  VStack(alignment: .leading, spacing: 4) {
                    HStack {
                      Text(finding.type.capitalized.replacingOccurrences(of: "_", with: " "))
                        .font(.system(size: 16, weight: .bold))
                        .foregroundStyle(ColorTokens.ik)
                      Spacer()
                      Text(finding.severity.capitalized)
                        .font(.system(size: 11, weight: .bold))
                        .textCase(.uppercase)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(severityColor(finding.severity).opacity(0.15))
                        .foregroundStyle(severityColor(finding.severity))
                        .clipShape(Capsule())
                    }
                    
                    Text(finding.description)
                      .font(TypographyTokens.caption)
                      .foregroundStyle(ColorTokens.st)
                      .multilineTextAlignment(.leading)
                      .lineLimit(2)
                  }
                }
                .padding(16)
                .background(
                  RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(ColorTokens.sf)
                    .shadow(color: Color.black.opacity(0.03), radius: 6, x: 0, y: 2)
                )
              }
              .buttonStyle(.plain)
            }
          }
        }
      }
    }
    .onAppear {
      withAnimation(.spring(response: 1.5, dampingFraction: 0.8, blendDuration: 0)) {
        animatedScore = Double(result.score)
      }
    }
    .sheet(item: Binding(
      get: { selectedFinding.map { FindingIdentifiableWrapper(finding: $0) } },
      set: { selectedFinding = $0?.finding }
    )) { wrapper in
      FindingDetailSheet(finding: wrapper.finding)
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

}

