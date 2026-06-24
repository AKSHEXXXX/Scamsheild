import SwiftUI

@MainActor
final class AppEnvironment: ObservableObject {
  let authService: SupabaseAuthService
  let apiClient: APIClient
  let networkMonitor: NetworkMonitor

  let submissionViewModel: SubmissionViewModel
  let historyViewModel: HistoryViewModel
  let settingsViewModel: SettingsViewModel
  let authViewModel: AuthViewModel

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
    // Passed to SubmissionViewModel so it can recover from expired tokens before
    // hitting auth-gated endpoints (e.g. /api/v1/feedback).
    let refreshTokenAction: () async throws -> Void = {
      try await authService.refreshAccessToken()
      apiClient.setAuthToken(authService.accessToken)
    }

    // View Models
    self.submissionViewModel = SubmissionViewModel(
      fetchConfigurationUseCase: fetchConfig,
      submitAnalysisUseCase: submitAnalysis,
      submitFeedbackUseCase: submitFeedback,
      saveHistoryEntryUseCase: saveHistory,
      refreshTokenAction: refreshTokenAction
    )

    self.historyViewModel = HistoryViewModel(
      loadHistoryUseCase: loadHistory,
      deleteHistoryEntryUseCase: deleteHistory
    )

    self.settingsViewModel = SettingsViewModel(
      loadHistoryUseCase: loadHistory,
      clearHistoryUseCase: clearHistory
    )

    self.authViewModel = AuthViewModel(authService: authService)
  }

  func syncAuthToken() {
    apiClient.setAuthToken(authService.accessToken)
  }
}
