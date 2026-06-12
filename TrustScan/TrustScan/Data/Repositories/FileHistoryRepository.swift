import Foundation

actor FileHistoryRepository: HistoryRepositoryPort {
  private let fileManager: FileManager
  private let fileName = "history.json"

  init(fileManager: FileManager = .default) {
    self.fileManager = fileManager
  }

  func loadHistory() async throws -> [HistoryEntry] {
    try readEntries()
  }

  func save(result: AnalysisResult, thumbnailData: Data?) async throws {
    var entries = try readEntries()
    entries.removeAll { $0.analysisId == result.id }

    let entry = HistoryEntry(
      id: UUID(),
      analysisId: result.id,
      verdict: result.verdict,
      threatScore: result.threatScore,
      analyzedAt: result.analysisTimestamp,
      summary: result.summary,
      thumbnailData: thumbnailData,
      resultSnapshot: result
    )

    entries.insert(entry, at: 0)
    try write(entries)
  }

  func delete(entryID: UUID) async throws {
    let filtered = try readEntries().filter { $0.id != entryID }
    try write(filtered)
  }

  func deleteAll() async throws {
    try write([])
  }

  private func readEntries() throws -> [HistoryEntry] {
    let url = try storageURL()

    guard fileManager.fileExists(atPath: url.path) else {
      return []
    }

    let data = try Data(contentsOf: url)
    let decoder = JSONDecoder()
    decoder.dateDecodingStrategy = .iso8601
    return try decoder.decode([HistoryEntry].self, from: data)
      .sorted { $0.analyzedAt > $1.analyzedAt }
  }

  private func write(_ entries: [HistoryEntry]) throws {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    encoder.dateEncodingStrategy = .iso8601

    let url = try storageURL()
    let data = try encoder.encode(entries)
    try data.write(to: url, options: [.atomic])
  }

  private func storageURL() throws -> URL {
    guard let directory = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
      throw AppError.persistenceFailure
    }

    let appDirectory = directory.appendingPathComponent("TrustScan", isDirectory: true)

    if !fileManager.fileExists(atPath: appDirectory.path) {
      try fileManager.createDirectory(at: appDirectory, withIntermediateDirectories: true)
    }

    return appDirectory.appendingPathComponent(fileName)
  }
}
