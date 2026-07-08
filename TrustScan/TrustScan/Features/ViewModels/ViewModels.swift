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
  // True when client-side pattern matching detects a likely backend miss
  @Published var clientOverrideActive = false
  private let fetchConfigurationUseCase: FetchConfigurationUseCase
  private let submitAnalysisUseCase: SubmitAnalysisUseCase
  private let submitFeedbackUseCase: SubmitFeedbackUseCase
  private let saveHistoryEntryUseCase: SaveHistoryEntryUseCase
  private let refreshTokenAction: () async throws -> Void
  private let reloadHistoryAction: () async -> Void

  init(
    fetchConfigurationUseCase: FetchConfigurationUseCase,
    submitAnalysisUseCase: SubmitAnalysisUseCase,
    submitFeedbackUseCase: SubmitFeedbackUseCase,
    saveHistoryEntryUseCase: SaveHistoryEntryUseCase,
    refreshTokenAction: @escaping () async throws -> Void = {},
    reloadHistoryAction: @escaping () async -> Void = {}
  ) {
    self.fetchConfigurationUseCase = fetchConfigurationUseCase
    self.submitAnalysisUseCase = submitAnalysisUseCase
    self.submitFeedbackUseCase = submitFeedbackUseCase
    self.saveHistoryEntryUseCase = saveHistoryEntryUseCase
    self.refreshTokenAction = refreshTokenAction
    self.reloadHistoryAction = reloadHistoryAction
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
      AnalyticsManager.shared.capture(event: "camera_opened")
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

    AnalyticsManager.shared.capture(event: "image_selected")
    selectedImageData = data
    state = .idle
  }

  func analyzeSelectedImage() async {
    guard let selectedImageData else {
      state = .error(.invalidImage)
      return
    }

    state = .loading(message: "Analyzing your image…")
    clientOverrideActive = false
    
    let startTime = Date()
    AnalyticsManager.shared.capture(event: "scan_started", properties: ["type": "image"])
    AnalyticsManager.shared.capture(event: "analysis_started", properties: ["type": "image"])

    do {
      guard let uiImage = UIImage(data: selectedImageData) else {
        throw AppError.invalidImage
      }

      let (result, sourceString) = try await submitAnalysisUseCase(
        image: uiImage,
        fileName: "scan-\(UUID().uuidString).jpg"
      )

      ocrSource = sourceString
      // Check if client-side signals override the backend verdict
      clientOverrideActive = result.clientDetectedMiss
      state = .success(result)
      
      let duration = Date().timeIntervalSince(startTime)
      AnalyticsManager.shared.capture(event: "analysis_completed", properties: [
          "type": "image",
          "scan_duration": duration,
          "result": result.verdict.rawValue,
          "threat_score": result.score
      ])

      do {
        try await saveHistoryEntryUseCase(
          result: result,
          thumbnailData: makeThumbnailData(from: selectedImageData)
        )
        await reloadHistoryAction()
      } catch {
        // Silent failure — result still displays
      }
    } catch AppError.dailyLimitReached(_, let resetsAt) {
      dailyLimitResetTime = resetsAt
      showDailyLimitAlert = true
      AnalyticsManager.shared.capture(event: "api_request_failed", properties: ["error": "daily_limit_reached"])
    } catch let appError as AppError {
      state = .error(appError)
      AnalyticsManager.shared.capture(event: "analysis_failed", properties: ["error": appError.localizedDescription])
    } catch {
      state = .error(.unexpected(message: error.localizedDescription))
      AnalyticsManager.shared.capture(event: "analysis_failed", properties: ["error": error.localizedDescription])
    }
  }

  func analyzeQR(payload: String) async {
    guard !payload.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
      state = .error(.unexpected(message: "The QR code appears to be empty. Please try scanning a different QR code."))
      return
    }
    state = .loading(message: "Checking QR Code…")
    clientOverrideActive = false
    
    let startTime = Date()
    AnalyticsManager.shared.capture(event: "scan_started", properties: ["type": "qr"])
    AnalyticsManager.shared.capture(event: "analysis_started", properties: ["type": "qr"])

    do {
      let (result, sourceString) = try await submitAnalysisUseCase.analyzeQR(payload: payload)

      ocrSource = sourceString
      clientOverrideActive = result.clientDetectedMiss
      state = .success(result)
      
      let duration = Date().timeIntervalSince(startTime)
      AnalyticsManager.shared.capture(event: "analysis_completed", properties: [
          "type": "qr",
          "scan_duration": duration,
          "result": result.verdict.rawValue,
          "threat_score": result.score
      ])

      do {
        // Thumbnail generation is nil for QR scan, but we can pass it
        try await saveHistoryEntryUseCase(
          result: result,
          thumbnailData: nil
        )
        await reloadHistoryAction()
      } catch {
        // Silent failure
      }
    } catch AppError.dailyLimitReached(_, let resetsAt) {
      dailyLimitResetTime = resetsAt
      showDailyLimitAlert = true
      AnalyticsManager.shared.capture(event: "api_request_failed", properties: ["error": "daily_limit_reached"])
    } catch let appError as AppError {
      state = .error(appError)
      AnalyticsManager.shared.capture(event: "analysis_failed", properties: ["error": appError.localizedDescription])
    } catch {
      state = .error(.unexpected(message: error.localizedDescription))
      AnalyticsManager.shared.capture(event: "analysis_failed", properties: ["error": error.localizedDescription])
    }
  }

  func resetFlow() {
    selectedImageData = nil
    ocrSource = ""
    clientOverrideActive = false
    state = .idle
  }

  func submitFeedback(scanId: String, label: String, completion: @escaping (Bool) -> Void) {
    Task {
      do {
        try? await refreshTokenAction()
        do {
          try await submitFeedbackUseCase.execute(scanId: scanId, label: label)
        } catch AppError.authenticationRequired {
          // Token expired despite proactive refresh — do one hard refresh and retry.
          try await refreshTokenAction()
          try await submitFeedbackUseCase.execute(scanId: scanId, label: label)
        }
        completion(true)
      } catch {
        completion(false)
      }
    }
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
    guard text.trimmingCharacters(in: .whitespacesAndNewlines).count >= 10 else {
      state = .error(.unexpected(message: "Please enter at least 10 characters of text to analyze."))
      return
    }
    state = .loading(message: "Analyzing text…")
    clientOverrideActive = false
    
    let startTime = Date()
    AnalyticsManager.shared.capture(event: "scan_started", properties: ["type": "text"])
    AnalyticsManager.shared.capture(event: "analysis_started", properties: ["type": "text"])
    
    // Preflight: log if obvious scam patterns are detected before API call
    _ = submitAnalysisUseCase.preflightScamCheck(text)
    do {
      let (result, sourceString) = try await submitAnalysisUseCase.analyzeText(text)

      ocrSource = sourceString
      clientOverrideActive = result.clientDetectedMiss
      state = .success(result)
      
      let duration = Date().timeIntervalSince(startTime)
      AnalyticsManager.shared.capture(event: "analysis_completed", properties: [
          "type": "text",
          "scan_duration": duration,
          "result": result.verdict.rawValue,
          "threat_score": result.score
      ])

      try? await saveHistoryEntryUseCase(result: result, thumbnailData: nil)
      await reloadHistoryAction()
    } catch AppError.dailyLimitReached(_, let resetsAt) {
      dailyLimitResetTime = resetsAt
      showDailyLimitAlert = true
      AnalyticsManager.shared.capture(event: "api_request_failed", properties: ["error": "daily_limit_reached"])
    } catch let appError as AppError {
      state = .error(appError)
      AnalyticsManager.shared.capture(event: "analysis_failed", properties: ["error": appError.localizedDescription])
    } catch {
      state = .error(.unexpected(message: error.localizedDescription))
      AnalyticsManager.shared.capture(event: "analysis_failed", properties: ["error": error.localizedDescription])
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

  func loadHistory(forceLoading: Bool = false, limit: Int? = nil) async {
    if forceLoading || isInitialState {
      state = .loading(message: "Loading your scans…")
    }

    do {
      let entries = try await loadHistoryUseCase(limit: limit)
      state = entries.isEmpty ? .empty : .success(entries)
    } catch {
      state = .error(.unexpected(message: "We couldn't load local scan history."))
    }
  }

  func delete(entryID: UUID) async {
    // Optimistically remove before the disk write so the UI responds instantly
    if case let .success(entries) = state {
      let updated = entries.filter { $0.id != entryID }
      state = updated.isEmpty ? .empty : .success(updated)
    }
    do {
      try await deleteHistoryEntryUseCase(entryID: entryID)
    } catch {
      // Roll back by reloading the real state
      await loadHistory(forceLoading: true)
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
      AnalyticsManager.shared.capture(event: "settings_updated", properties: ["action": "clear_history"])
    } catch {
      lastOperationError = "Local history could not be cleared."
    }
  }
}
