import Foundation

actor FileHistoryRepository: HistoryRepositoryPort {
  private let fileManager: FileManager
  private let fileName = "history.json"

  init(fileManager: FileManager = .default) {
    self.fileManager = fileManager
  }

  func loadHistory(limit: Int? = nil) async throws -> [HistoryEntry] {
    try readEntries(limit: limit)
  }

  func save(result: AnalysisResult, thumbnailData: Data?) async throws {
    var entries = try readEntries()
    entries.removeAll { $0.analysisId == result.id }

    let entry = HistoryEntry(
      id: UUID(),
      analysisId: result.id,
      verdict: result.verdict,
      score: result.score,
      analyzedAt: result.analysisTimestamp,
      summary: result.summary,
      thumbnailData: thumbnailData,
      resultSnapshot: result
    )

    entries.insert(entry, at: 0)
    // Keep at most 100 entries to bound file size (thumbnails are ~10–50 KB each)
    if entries.count > 100 { entries = Array(entries.prefix(100)) }
    try write(entries)
  }

  func delete(entryID: UUID) async throws {
    let filtered = try readEntries().filter { $0.id != entryID }
    try write(filtered)
  }

  func deleteAll() async throws {
    try write([])
  }

  private func readEntries(limit: Int? = nil) throws -> [HistoryEntry] {
    let url = try storageURL()

    guard fileManager.fileExists(atPath: url.path) else {
      return []
    }

    do {
      let data = try Data(contentsOf: url)
      let decoder = JSONDecoder()
      decoder.dateDecodingStrategy = .iso8601
      let entries = try decoder.decode([HistoryEntry].self, from: data)
        .sorted { $0.analyzedAt > $1.analyzedAt }
      if let limit {
        return Array(entries.prefix(max(limit, 0)))
      }
      return entries
    } catch {
      // File is corrupted or from an incompatible version — remove and treat as empty
      try? fileManager.removeItem(at: url)
      return []
    }
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
