import SwiftUI

// CI trigger: verify iOS workflow execution
@MainActor
final class AppEnvironment: ObservableObject {
  let authService: SupabaseAuthService
  let apiClient: APIClient
  let networkMonitor: NetworkMonitor

  let submissionViewModel: SubmissionViewModel
  let historyViewModel: HistoryViewModel
  let settingsViewModel: SettingsViewModel
  @Published var authViewModel: AuthViewModel

  @MainActor
  init() {
    let authService = SupabaseAuthService()
    let apiClient = APIClient()
    let networkMonitor = NetworkMonitor()

    self.authService = authService
    self.apiClient = apiClient
    self.networkMonitor = networkMonitor

    // Pass auth token to API client
    if let token = authService.accessToken {
      apiClient.setAuthToken(token)
    }

    // Repositories
    let remoteAnalysis = RemoteAnalysisRepository(apiClient: apiClient)
    let historyRepo = FileHistoryRepository()
    let configRepo = RemoteConfigurationRepository(apiClient: apiClient)

    // Use cases
    let submitAnalysis = SubmitAnalysisUseCase(analysisRepository: remoteAnalysis)
    let submitFeedback = SubmitFeedbackUseCase(repository: remoteAnalysis)
    let fetchConfig = FetchConfigurationUseCase(configurationRepository: configRepo)
    let loadHistory = LoadHistoryUseCase(historyRepository: historyRepo)
    let saveHistory = SaveHistoryEntryUseCase(historyRepository: historyRepo)
    let deleteHistory = DeleteHistoryEntryUseCase(historyRepository: historyRepo)
    let clearHistory = ClearHistoryUseCase(historyRepository: historyRepo)

    // Closure that refreshes the Supabase JWT and immediately syncs it to APIClient.
    // Guard against nil: if accessToken is nil after refresh, keep the existing token.
    let refreshTokenAction: () async throws -> Void = {
      try await authService.refreshAccessToken()
      if let token = authService.accessToken { apiClient.setAuthToken(token) }
    }

    // View Models — historyVm is a local let so the reloadHistoryAction closure can capture it
    // before self.historyViewModel is assigned.
    let historyVm = HistoryViewModel(
      loadHistoryUseCase: loadHistory,
      deleteHistoryEntryUseCase: deleteHistory
    )

    let reloadHistoryAction: () async -> Void = {
      await historyVm.loadHistory(forceLoading: false, limit: 20)
    }

    self.submissionViewModel = SubmissionViewModel(
      fetchConfigurationUseCase: fetchConfig,
      submitAnalysisUseCase: submitAnalysis,
      submitFeedbackUseCase: submitFeedback,
      saveHistoryEntryUseCase: saveHistory,
      refreshTokenAction: refreshTokenAction,
      reloadHistoryAction: reloadHistoryAction
    )

    self.historyViewModel = historyVm

    self.settingsViewModel = SettingsViewModel(
      loadHistoryUseCase: loadHistory,
      clearHistoryUseCase: clearHistory
    )

    self.authViewModel = AuthViewModel(authService: authService)
  }

  func syncAuthToken() {
    if let token = authService.accessToken { apiClient.setAuthToken(token) }
  }
}
