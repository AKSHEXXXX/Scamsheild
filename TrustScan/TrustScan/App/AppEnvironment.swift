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
    let localAnalysis = LocalAnalysisRepository()
    let historyRepo = FileHistoryRepository()
    let configRepo = RemoteConfigurationRepository(apiClient: apiClient)

    // Use cases
    let submitAnalysis = SubmitAnalysisUseCase(analysisRepository: remoteAnalysis)
    let fetchConfig = FetchConfigurationUseCase(configurationRepository: configRepo)
    let loadHistory = LoadHistoryUseCase(historyRepository: historyRepo)
    let saveHistory = SaveHistoryEntryUseCase(historyRepository: historyRepo)
    let deleteHistory = DeleteHistoryEntryUseCase(historyRepository: historyRepo)
    let clearHistory = ClearHistoryUseCase(historyRepository: historyRepo)

    // View Models
    self.submissionViewModel = SubmissionViewModel(
      fetchConfigurationUseCase: fetchConfig,
      submitAnalysisUseCase: submitAnalysis,
      saveHistoryEntryUseCase: saveHistory
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
