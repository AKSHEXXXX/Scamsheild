import Foundation

struct FetchConfigurationUseCase {
  private let configurationRepository: any ConfigurationRepositoryPort

  init(configurationRepository: any ConfigurationRepositoryPort) {
    self.configurationRepository = configurationRepository
  }

  func callAsFunction() async -> AppConfiguration {
    await configurationRepository.fetchConfiguration()
  }
}
