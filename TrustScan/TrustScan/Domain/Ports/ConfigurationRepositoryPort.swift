import Foundation

protocol ConfigurationRepositoryPort {
  func fetchConfiguration() async -> AppConfiguration
}
