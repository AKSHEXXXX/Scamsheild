import SwiftUI

enum HistoryFilter: String, CaseIterable {
  case all = "All"
  case highRisk = "High Risk"
  case safe = "Safe"
  case suspicious = "Suspicious"
}

struct HistoryListView: View {
  @ObservedObject var viewModel: HistoryViewModel
  let onScanRequested: () -> Void
  @State private var selectedFilter: HistoryFilter = .all
  var preSelectedFilter: HistoryFilter?

  init(viewModel: HistoryViewModel, onScanRequested: @escaping () -> Void, preSelectedFilter: HistoryFilter? = nil) {
    self.viewModel = viewModel
    self.onScanRequested = onScanRequested
    self.preSelectedFilter = preSelectedFilter
  }

  private var filteredEntries: [HistoryEntry] {
    guard case let .success(entries) = viewModel.state else { return [] }
    switch selectedFilter {
    case .all:
      return entries
    case .highRisk:
      return entries.filter { $0.verdict == .scam }
    case .safe:
      return entries.filter { $0.verdict == .safe }
    case .suspicious:
      return entries.filter { $0.verdict == .suspicious }
    }
  }

  var body: some View {
    VStack(spacing: 0) {
      // Filter chips
      ScrollView(.horizontal, showsIndicators: false) {
        HStack(spacing: SpacingTokens.small) {
          ForEach(HistoryFilter.allCases, id: \.self) { filter in
            Button {
              withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                selectedFilter = filter
              }
            } label: {
              Text(filter.rawValue)
                .font(.system(size: 14, weight: .semibold, design: .rounded))
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
            }
            .buttonStyle(.plain)
            .foregroundStyle(selectedFilter == filter ? .white : ColorTokens.acc)
            .background(selectedFilter == filter ? ColorTokens.acc : ColorTokens.sf)
            .clipShape(Capsule())
            .overlay(
              Capsule().stroke(
                selectedFilter == filter ? Color.clear : ColorTokens.acc.opacity(0.4),
                lineWidth: 1
              )
            )
          }
        }
        .padding(.horizontal, SpacingTokens.large)
        .padding(.vertical, SpacingTokens.small)
      }

      Group {
        switch viewModel.state {
        case let .loading(message):
          VStack(spacing: SpacingTokens.medium) {
            ProgressView()
            Text(message ?? "Loading…")
              .font(TypographyTokens.body)
              .foregroundStyle(ColorTokens.st)
          }
          .frame(maxWidth: .infinity, maxHeight: .infinity)
          .background(ColorTokens.bg)

        case .success:
          if filteredEntries.isEmpty {
            emptyFilterState
          } else {
            List {
              ForEach(filteredEntries) { entry in
                NavigationLink(value: entry) {
                  HistoryRow(entry: entry)
                }
                .swipeActions {
                  Button(role: .destructive) {
                    Task { await viewModel.delete(entryID: entry.id) }
                  } label: {
                    Label("Delete", systemImage: "trash")
                  }
                }
              }
            }
            .scrollContentBackground(.hidden)
            .background(ColorTokens.bg)
          }

      case .empty:
        EmptyStateView(
          icon: "clock.badge.exclamationmark",
          title: "No scans yet",
          description: "Run your first screenshot through the scanner and it will show up here automatically.",
          actionTitle: "Start Scanning",
          action: { onScanRequested() }
        )

      case .idle:
        ColorTokens.bg

      case let .error(error):
        VStack(spacing: SpacingTokens.medium) {
          Text(error.errorDescription ?? "Something went wrong.")
            .font(TypographyTokens.body)
            .foregroundStyle(ColorTokens.ik)

          Button("Reload") {
            Task { await viewModel.loadHistory(forceLoading: true) }
          }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(ColorTokens.bg)
      }
      }
    }
    .navigationTitle("History")
    .navigationDestination(for: HistoryEntry.self) { entry in
      ScrollView {
        AnalysisResultView(result: entry.resultSnapshot)
          .padding(SpacingTokens.large)
      }
      .background(ColorTokens.bg.ignoresSafeArea())
      .navigationTitle("Scan Result")
      .navigationBarTitleDisplayMode(.inline)
    }
    .safeAreaInset(edge: .bottom, spacing: 0) {
      Color.clear.frame(height: 16)
    }
    .onAppear {
      if let preset = preSelectedFilter {
        selectedFilter = preset
      }
    }
    .task {
      await viewModel.loadHistory(forceLoading: true)
    }
    .trackScreen(name: "History")
  }

  private var emptyFilterState: some View {
    VStack(spacing: SpacingTokens.medium) {
      Image(systemName: "line.3.horizontal.decrease.circle")
        .font(.system(size: 40))
        .foregroundStyle(ColorTokens.st.opacity(0.4))
      Text("No \(selectedFilter.rawValue.lowercased()) scans")
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.st)
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity)
    .background(ColorTokens.bg)
  }
}

struct HistoryRow: View {
  let entry: HistoryEntry

  var body: some View {
    HStack(spacing: SpacingTokens.medium) {
      thumbnail

      VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
        VerdictBadge(verdict: entry.verdict)

        Text("Risk score \(entry.score)% · \(entry.resultSnapshot.topSignal?.replacingOccurrences(of: "_", with: " ") ?? "Scan")")
          .font(TypographyTokens.body)
          .foregroundStyle(ColorTokens.ik)
          .lineLimit(1)

        Text(entry.analyzedAt.formatted(date: .abbreviated, time: .shortened))
          .font(TypographyTokens.caption)
          .foregroundStyle(ColorTokens.st)
      }
    }
    .padding(.vertical, SpacingTokens.xSmall)
    .accessibilityLabel("\(entry.verdict.displayTitle) scan from \(entry.analyzedAt.formatted())")
  }

  @ViewBuilder
  private var thumbnail: some View {
    if let thumbnailData = entry.thumbnailData, let image = UIImage(data: thumbnailData) {
      Image(uiImage: image)
        .resizable()
        .scaledToFill()
        .frame(width: 64, height: 64)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    } else {
      RoundedRectangle(cornerRadius: 16, style: .continuous)
        .fill(entry.verdict.tintColor.opacity(0.14))
        .frame(width: 64, height: 64)
        .overlay {
          Image(systemName: entry.verdict.iconName)
            .foregroundStyle(entry.verdict.tintColor)
        }
    }
  }
}
