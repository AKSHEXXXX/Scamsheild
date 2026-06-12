import Foundation

struct RemoteConfigurationRepository: ConfigurationRepositoryPort {
  private let apiClient: APIClient

  func fetchConfiguration() async -> AppConfiguration {
    do {
      let dto: ConfigOutDTO = try await apiClient.get(path: "/api/v1/config")
      return dto.toDomain()
    } catch {
      return .defaultValue
    }
  }

  init(apiClient: APIClient) {
    self.apiClient = apiClient
  }
}
