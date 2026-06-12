import SwiftUI
import PhotosUI
import UIKit

// MARK: - Submission ViewModel

@MainActor
final class SubmissionViewModel: ObservableObject {
  @Published var configuration = AppConfiguration.defaultValue
  @Published var state: ViewState<AnalysisResult> = .idle
  @Published var selectedImageData: Data?
  @Published var isShowingCamera = false
  @Published var isShowingShareSheet = false
  @Published var isShowingPhotoDenied = false
  @Published var isShowingCameraDenied = false

  private let fetchConfigurationUseCase: FetchConfigurationUseCase
  private let submitAnalysisUseCase: SubmitAnalysisUseCase
  private let saveHistoryEntryUseCase: SaveHistoryEntryUseCase

  init(
    fetchConfigurationUseCase: FetchConfigurationUseCase,
    submitAnalysisUseCase: SubmitAnalysisUseCase,
    saveHistoryEntryUseCase: SaveHistoryEntryUseCase
  ) {
    self.fetchConfigurationUseCase = fetchConfigurationUseCase
    self.submitAnalysisUseCase = submitAnalysisUseCase
    self.saveHistoryEntryUseCase = saveHistoryEntryUseCase
  }

  var previewImage: UIImage? {
    guard let selectedImageData else { return nil }
    return UIImage(data: selectedImageData)
  }

  func loadConfiguration() async {
    configuration = await fetchConfigurationUseCase()
  }

  func checkPhotoPermissionAndPick() -> Bool {
    let status = PhotoPermissionManager.currentStatus
    switch status {
    case .denied, .restricted:
      isShowingPhotoDenied = true
      return false
    default:
      return true
    }
  }

  func checkCameraPermission() {
    let status = CameraPermissionManager.currentStatus
    switch status {
    case .denied, .restricted:
      isShowingCameraDenied = true
    default:
      isShowingCamera = true
    }
  }

  func handlePickedImage(_ data: Data) {
    let maxMegabytes = max(configuration.maxImageFileSizeBytes / 1_000_000, 1)

    guard UIImage(data: data) != nil else {
      state = .error(.invalidImage)
      return
    }

    guard data.count <= configuration.maxImageFileSizeBytes else {
      state = .error(.imageTooLarge(maxMegabytes: maxMegabytes))
      return
    }

    selectedImageData = data
    state = .idle
  }

  func analyzeSelectedImage() async {
    guard let selectedImageData else {
      state = .error(.invalidImage)
      return
    }

    state = .loading(message: "Analyzing your image…")

    do {
      let result = try await submitAnalysisUseCase(
        image: PreparedImagePayload(
          data: selectedImageData,
          mimeType: "image/jpeg",
          fileName: "scan-\(UUID().uuidString).jpg"
        )
      )

      state = .success(result)

      do {
        try await saveHistoryEntryUseCase(
          result: result,
          thumbnailData: makeThumbnailData(from: selectedImageData)
        )
      } catch {
        // Silent failure — result still displays
      }
    } catch let appError as AppError {
      state = .error(appError)
    } catch {
      state = .error(.unexpected(message: error.localizedDescription))
    }
  }

  func resetFlow() {
    selectedImageData = nil
    state = .idle
  }

  private func makeThumbnailData(from data: Data) -> Data? {
    guard let image = UIImage(data: data) else { return nil }
    let targetWidth: CGFloat = 240
    let scale = targetWidth / max(image.size.width, 1)
    let targetHeight = max(image.size.height * scale, 1)
    let size = CGSize(width: targetWidth, height: targetHeight)
    let renderer = UIGraphicsImageRenderer(size: size)
    let thumbnail = renderer.image { _ in
      image.draw(in: CGRect(origin: .zero, size: size))
    }
    return thumbnail.jpegData(compressionQuality: 0.72)
  }
}

// MARK: - History ViewModel

@MainActor
final class HistoryViewModel: ObservableObject {
  @Published var state: ViewState<[HistoryEntry]> = .idle

  private let loadHistoryUseCase: LoadHistoryUseCase
  private let deleteHistoryEntryUseCase: DeleteHistoryEntryUseCase

  init(
    loadHistoryUseCase: LoadHistoryUseCase,
    deleteHistoryEntryUseCase: DeleteHistoryEntryUseCase
  ) {
    self.loadHistoryUseCase = loadHistoryUseCase
    self.deleteHistoryEntryUseCase = deleteHistoryEntryUseCase
  }

  func loadHistory(forceLoading: Bool = false) async {
    if forceLoading || isInitialState {
      state = .loading(message: "Loading your scans…")
    }

    do {
      let entries = try await loadHistoryUseCase()
      state = entries.isEmpty ? .empty : .success(entries)
    } catch {
      state = .error(.unexpected(message: "We couldn't load local scan history."))
    }
  }

  func delete(entryID: UUID) async {
    do {
      try await deleteHistoryEntryUseCase(entryID: entryID)
      await loadHistory(forceLoading: false)
    } catch {
      state = .error(.unexpected(message: "We couldn't delete this scan."))
    }
  }

  // Recent scans for home screen
  func recentEntries(limit: Int = 3) -> [HistoryEntry] {
    if case let .success(entries) = state {
      return Array(entries.prefix(limit))
    }
    return []
  }

  private var isInitialState: Bool {
    if case .idle = state { return true }
    return false
  }
}

// MARK: - Settings ViewModel

@MainActor
final class SettingsViewModel: ObservableObject {
  @Published var storedScanCount = 0
  @Published var lastOperationError: String?

  private let loadHistoryUseCase: LoadHistoryUseCase
  private let clearHistoryUseCase: ClearHistoryUseCase

  init(
    loadHistoryUseCase: LoadHistoryUseCase,
    clearHistoryUseCase: ClearHistoryUseCase
  ) {
    self.loadHistoryUseCase = loadHistoryUseCase
    self.clearHistoryUseCase = clearHistoryUseCase
  }

  func refresh() async {
    do {
      storedScanCount = try await loadHistoryUseCase().count
      lastOperationError = nil
    } catch {
      lastOperationError = "Local history could not be read."
    }
  }

  func clearHistory() async {
    do {
      try await clearHistoryUseCase()
      storedScanCount = 0
      lastOperationError = nil
    } catch {
      lastOperationError = "Local history could not be cleared."
    }
  }
}
