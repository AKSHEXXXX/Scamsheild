import SwiftUI

struct HistoryListView: View {
  @ObservedObject var viewModel: HistoryViewModel
  let onScanRequested: () -> Void

  var body: some View {
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

      case let .success(entries):
        List {
          ForEach(entries) { entry in
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
    .task {
      await viewModel.loadHistory(forceLoading: true)
    }
  }
}

struct HistoryRow: View {
  let entry: HistoryEntry

  var body: some View {
    HStack(spacing: SpacingTokens.medium) {
      thumbnail

      VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
        VerdictBadge(verdict: entry.verdict)

        Text(entry.summary)
          .font(TypographyTokens.body)
          .foregroundStyle(ColorTokens.ik)
          .lineLimit(2)

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
