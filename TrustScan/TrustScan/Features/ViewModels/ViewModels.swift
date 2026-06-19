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
  @Published var ocrSource: String = ""
  @Published var showDailyLimitAlert = false
  @Published var dailyLimitResetTime: String = ""

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
      guard let uiImage = UIImage(data: selectedImageData) else {
        throw AppError.invalidImage
      }

      let (result, sourceString) = try await submitAnalysisUseCase(
        image: uiImage,
        fileName: "scan-\(UUID().uuidString).jpg"
      )

      ocrSource = sourceString
      state = .success(result)

      do {
        try await saveHistoryEntryUseCase(
          result: result,
          thumbnailData: makeThumbnailData(from: selectedImageData)
        )
      } catch {
        // Silent failure — result still displays
      }
    } catch AppError.dailyLimitReached(_, let resetsAt) {
      dailyLimitResetTime = resetsAt
      showDailyLimitAlert = true
    } catch let appError as AppError {
      state = .error(appError)
    } catch {
      state = .error(.unexpected(message: error.localizedDescription))
    }
  }

  func analyzeQR(payload: String) async {
    state = .loading(message: "Checking QR Code…")

    do {
      let (result, sourceString) = try await submitAnalysisUseCase.analyzeQR(payload: payload)

      ocrSource = sourceString
      state = .success(result)

      do {
        // Thumbnail generation is nil for QR scan, but we can pass it
        try await saveHistoryEntryUseCase(
          result: result,
          thumbnailData: nil
        )
      } catch {
        // Silent failure
      }
    } catch AppError.dailyLimitReached(_, let resetsAt) {
      dailyLimitResetTime = resetsAt
      showDailyLimitAlert = true
    } catch let appError as AppError {
      state = .error(appError)
    } catch {
      state = .error(.unexpected(message: error.localizedDescription))
    }
  }

  func resetFlow() {
    selectedImageData = nil
    ocrSource = ""
    state = .idle
  }

  func handleSharedFile(filename: String) {
    guard let groupURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: "group.com.binaryz.scamshield") else {
      state = .error(.unexpected(message: "App Group not configured"))
      return
    }
    let fileURL = groupURL.appendingPathComponent(filename)
    
    do {
      let data = try Data(contentsOf: fileURL)
      self.selectedImageData = data
      
      // Clean up the temporary shared file
      try? FileManager.default.removeItem(at: fileURL)
      
      // Auto-trigger analysis
      Task {
        await self.analyzeSelectedImage()
      }
    } catch {
      state = .error(.unexpected(message: "Failed to read shared image: \(error.localizedDescription)"))
    }
  }

  func handleSharedText(_ text: String) {
    Task {
      await self.analyzeText(text)
    }
  }

  func analyzeText(_ text: String) async {
    state = .loading(message: "Analyzing text…")
    do {
      // Create a temporary SubmissionUseCase for text?
      // Since SubmitAnalysisUseCase only takes UIImage, we can bypass it and use repo directly
      // However, we don't have access to repo directly in ViewModel, but we can inject it or add to AppEnvironment.
      // Wait, we can just add an analyzeText method to SubmitAnalysisUseCase!
      let (result, sourceString) = try await submitAnalysisUseCase.analyzeText(text)
      
      ocrSource = sourceString
      state = .success(result)
      
      try? await saveHistoryEntryUseCase(result: result, thumbnailData: nil)
    } catch AppError.dailyLimitReached(_, let resetsAt) {
      dailyLimitResetTime = resetsAt
      showDailyLimitAlert = true
    } catch let appError as AppError {
      state = .error(appError)
    } catch {
      state = .error(.unexpected(message: error.localizedDescription))
    }
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
