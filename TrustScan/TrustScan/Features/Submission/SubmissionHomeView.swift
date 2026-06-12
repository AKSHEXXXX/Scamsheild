import SwiftUI
import PhotosUI

struct SubmissionHomeView: View {
  @ObservedObject var viewModel: SubmissionViewModel
  @EnvironmentObject private var networkMonitor: NetworkMonitor
  @EnvironmentObject private var environment: AppEnvironment

  @State private var selectedPhotoItem: PhotosPickerItem?
  @State private var dismissedOfflineBanner = false

  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: SpacingTokens.large) {
        // Offline banner
        if !networkMonitor.isConnected && !dismissedOfflineBanner {
          OfflineBanner { dismissedOfflineBanner = true }
        }

        heroSection

        // Recent Scans
        let recentScans = environment.historyViewModel.recentEntries()
        if !recentScans.isEmpty {
          recentScansSection(entries: recentScans)
        }

        sourceSection

        if let previewImage = viewModel.previewImage {
          previewSection(image: previewImage)
        }

        stateSection
      }
      .padding(SpacingTokens.large)
    }
    .background(ColorTokens.bg.ignoresSafeArea())
    .navigationTitle("Scan")
    .sheet(isPresented: $viewModel.isShowingCamera) {
      CameraImagePicker { data in
        viewModel.handlePickedImage(data)
      }
      .ignoresSafeArea()
    }
    .sheet(isPresented: $viewModel.isShowingPhotoDenied) {
      PermissionPromptSheet(
        permissionType: "photos",
        headline: "Photo Access Required",
        bodyText: "TrustScan needs access to your photo library so you can select screenshots for analysis.",
        onOpenSettings: { openAppSettings() },
        onDismiss: { viewModel.isShowingPhotoDenied = false }
      )
    }
    .sheet(isPresented: $viewModel.isShowingCameraDenied) {
      PermissionPromptSheet(
        permissionType: "camera",
        headline: "Camera Access Required",
        bodyText: "TrustScan needs camera access so you can photograph a document or screen directly.",
        onOpenSettings: { openAppSettings() },
        onDismiss: { viewModel.isShowingCameraDenied = false }
      )
    }
    .onChange(of: selectedPhotoItem) { newItem in
      guard let newItem else { return }
      Task {
        if let data = try? await newItem.loadTransferable(type: Data.self) {
          viewModel.handlePickedImage(data)
        }
      }
    }
    .onChange(of: networkMonitor.isConnected) { connected in
      if connected { dismissedOfflineBanner = false }
    }
  }

  // MARK: - Sections

  private var heroSection: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.small) {
      Text("What looks suspicious today?")
        .font(TypographyTokens.hero)
        .foregroundStyle(ColorTokens.ik)

      Text("Upload a screenshot to check for scams instantly.")
        .font(TypographyTokens.body)
        .foregroundStyle(ColorTokens.st)

      HStack(spacing: SpacingTokens.small) {
        Label("No sign-in required", systemImage: "person.crop.circle.badge.checkmark")
        Label("Local history", systemImage: "internaldrive")
      }
      .font(TypographyTokens.caption)
      .foregroundStyle(ColorTokens.st)
    }
    .padding(SpacingTokens.large)
    .frame(maxWidth: .infinity, alignment: .leading)
    .background(
      RoundedRectangle(cornerRadius: 28, style: .continuous)
        .fill(
          LinearGradient(
            colors: [ColorTokens.sf, ColorTokens.sfm],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
          )
        )
    )
  }

  private func recentScansSection(entries: [HistoryEntry]) -> some View {
    VStack(alignment: .leading, spacing: SpacingTokens.small) {
      Text("Recent Scans")
        .font(TypographyTokens.sectionTitle)
        .foregroundStyle(ColorTokens.ik)

      ScrollView(.horizontal, showsIndicators: false) {
        HStack(spacing: SpacingTokens.medium) {
          ForEach(entries) { entry in
            recentScanCard(entry: entry)
          }
        }
      }
    }
  }

  private func recentScanCard(entry: HistoryEntry) -> some View {
    VStack(alignment: .leading, spacing: SpacingTokens.xSmall) {
      VerdictBadge(verdict: entry.verdict)

      Text(entry.summary)
        .font(TypographyTokens.caption)
        .foregroundStyle(ColorTokens.st)
        .lineLimit(2)

      Text(entry.analyzedAt.formatted(date: .abbreviated, time: .shortened))
        .font(.system(size: 11, weight: .regular, design: .rounded))
        .foregroundStyle(ColorTokens.st.opacity(0.7))
    }
    .padding(SpacingTokens.medium)
    .frame(width: 180, alignment: .leading)
    .background(
      RoundedRectangle(cornerRadius: 20, style: .continuous)
        .fill(ColorTokens.sf)
        .shadow(color: .black.opacity(0.04), radius: 8, y: 4)
    )
  }

  private var sourceSection: some View {
    VStack(alignment: .leading, spacing: SpacingTokens.small) {
      Text("Choose a source")
        .font(TypographyTokens.sectionTitle)
        .foregroundStyle(ColorTokens.ik)

      if viewModel.checkPhotoPermissionAndPick() || PhotoPermissionManager.currentStatus != .denied {
        PhotosPicker(
          selection: $selectedPhotoItem,
          matching: .images,
          preferredItemEncoding: .automatic
        ) {
          Label("Choose Screenshot", systemImage: "photo.badge.plus")
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
        .tint(ColorTokens.acc)
        .disabled(!networkMonitor.isConnected)
      } else {
        Button {
          viewModel.isShowingPhotoDenied = true
        } label: {
          Label("Choose Screenshot", systemImage: "photo.badge.plus")
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
        .tint(ColorTokens.acc)
      }

      Button {
        viewModel.checkCameraPermission()
      } label: {
        Label("Take Photo", systemImage: "camera")
          .frame(maxWidth: .infinity)
      }
      .buttonStyle(.bordered)
    }
  }

  private func previewSection(image: UIImage) -> some View {
    VStack(alignment: .leading, spacing: SpacingTokens.medium) {
      Text("Preview")
        .font(TypographyTokens.sectionTitle)
        .foregroundStyle(ColorTokens.ik)

      Image(uiImage: image)
        .resizable()
        .scaledToFit()
        .frame(maxWidth: .infinity)
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))

      HStack {
        Button("Analyze Screenshot") {
          Task { await viewModel.analyzeSelectedImage() }
        }
        .buttonStyle(.borderedProminent)
        .tint(ColorTokens.acc)
        .disabled(!networkMonitor.isConnected)

        Button("Start Over") {
          viewModel.resetFlow()
        }
        .buttonStyle(.bordered)
      }
    }
    .padding(SpacingTokens.large)
    .frame(maxWidth: .infinity, alignment: .leading)
    .background(
      RoundedRectangle(cornerRadius: 28, style: .continuous)
        .fill(ColorTokens.sf)
    )
  }

  @ViewBuilder
  private var stateSection: some View {
    switch viewModel.state {
    case let .loading(message):
      LoadingStateView(message: message ?? "Analyzing your image…")
        .frame(height: 300)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))

    case let .error(error):
      InlineErrorView(
        error: error,
        onRetry: viewModel.selectedImageData != nil ? {
          Task { await viewModel.analyzeSelectedImage() }
        } : nil,
        onDismiss: { viewModel.resetFlow() }
      )

    case let .success(result):
      AnalysisResultView(result: result) {
        viewModel.isShowingShareSheet = true
      }
      .sheet(isPresented: $viewModel.isShowingShareSheet) {
        ShareSheet(items: [shareText(for: result)])
      }

    case .idle, .empty:
      EmptyView()
    }
  }

  // MARK: - Helpers

  private func shareText(for result: AnalysisResult) -> String {
    """
    TrustScan result: \(result.verdict.displayTitle)
    Risk score: \(Int(result.threatScore * 100))%
    Summary: \(result.summary)

    This analysis is provided for informational purposes only.
    """
  }

  private func openAppSettings() {
    guard let settingsURL = URL(string: UIApplication.openSettingsURLString) else { return }
    UIApplication.shared.open(settingsURL)
  }
}
