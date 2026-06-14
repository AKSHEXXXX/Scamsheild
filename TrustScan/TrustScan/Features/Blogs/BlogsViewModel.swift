import Foundation

struct ScamArticle: Identifiable, Equatable {
  let id = UUID()
  let title: String
  let link: URL
  let pubDate: Date
  let source: String
  let sourceColor: String  // hex string for branding
  let category: ScamCategory
  let description: String?
  let thumbnailURL: URL?

  var relativeDate: String {
    let formatter = RelativeDateTimeFormatter()
    formatter.unitsStyle = .abbreviated
    return formatter.localizedString(for: pubDate, relativeTo: Date())
  }
}

enum ScamCategory: String, CaseIterable {
  case all        = "All"
  case phishing   = "Phishing"
  case investment = "Investment"
  case romance    = "Romance Scam"
  case techSupport = "Tech Support"
  case sms        = "SMS / OTP"
  case crypto     = "Crypto"
  case malware    = "Malware"
}

// MARK: - RSS Feed Sources

struct RSSFeedSource {
  let url: String
  let name: String
  let color: String  // hex

  static let all: [RSSFeedSource] = [
    RSSFeedSource(
      url: "https://feeds.feedburner.com/TheHackersNews",
      name: "The Hacker News",
      color: "#E74C3C"
    ),
    RSSFeedSource(
      url: "https://www.bleepingcomputer.com/feed/",
      name: "BleepingComputer",
      color: "#2980B9"
    ),
    RSSFeedSource(
      url: "https://krebsonsecurity.com/feed/",
      name: "Krebs on Security",
      color: "#27AE60"
    ),
    RSSFeedSource(
      url: "https://www.scamwatch.gov.au/news/rss",
      name: "Scamwatch",
      color: "#8E44AD"
    ),
    RSSFeedSource(
      url: "https://www.ic3.gov/RSS",
      name: "FBI IC3",
      color: "#2C3E50"
    ),
  ]
}

// MARK: - RSS XML Parser

class RSSParser: NSObject, XMLParserDelegate {
  let source: RSSFeedSource

  private var currentElement = ""
  private var currentTitle = ""
  private var currentLink = ""
  private var currentPubDate = ""
  private var currentDescription = ""
  private var currentThumbnailURL: String = ""
  private var insideItem = false

  var parsingArticles: [ScamArticle] = []

  init(source: RSSFeedSource) {
    self.source = source
  }

  func parser(_ parser: XMLParser, didStartElement elementName: String,
              namespaceURI: String?, qualifiedName qName: String?,
              attributes attributeDict: [String: String] = [:]) {
    let qn = qName ?? elementName  // use qualified name to catch media:content etc.
    currentElement = qn

    if elementName == "item" || elementName == "entry" {
      insideItem = true
      currentTitle = ""
      currentLink = ""
      currentPubDate = ""
      currentDescription = ""
      currentThumbnailURL = ""
    }

    // Capture image from <enclosure url="..." type="image/..."> (used by THN)
    if insideItem && qn == "enclosure" {
      let urlStr = attributeDict["url"] ?? ""
      let type   = attributeDict["type"] ?? ""
      if !urlStr.isEmpty && (type.hasPrefix("image") || type.isEmpty) {
        currentThumbnailURL = urlStr
      }
    }

    // <media:content url="..."> and <media:thumbnail url="..."> (Krebs, others)
    if insideItem && (qn == "media:content" || qn == "media:thumbnail") {
      if let urlStr = attributeDict["url"], !urlStr.isEmpty {
        currentThumbnailURL = urlStr
      }
    }

    // Atom <link href="...">  
    if insideItem && qn == "link" {
      if let href = attributeDict["href"], !href.isEmpty {
        currentLink = href
      }
    }
  }

  func parser(_ parser: XMLParser, foundCharacters string: String) {
    guard insideItem else { return }
    switch currentElement {
    case "title":         currentTitle       += string
    case "link":          currentLink        += string
    case "pubDate", "published", "updated":   currentPubDate    += string
    case "description", "summary",
         "content:encoded", "content": currentDescription += string
    default: break
    }
  }

  // Called for CDATA sections (descriptions in RSS are often CDATA)
  func parser(_ parser: XMLParser, foundCDATA CDATABlock: Data) {
    guard insideItem else { return }
    if let str = String(data: CDATABlock, encoding: .utf8) {
      switch currentElement {
      case "description", "summary", "content:encoded", "content":
        currentDescription += str
      default: break
      }
    }
  }

  func parser(_ parser: XMLParser, didEndElement elementName: String,
              namespaceURI: String?, qualifiedName qName: String?) {
    if elementName == "item" || elementName == "entry" {
      insideItem = false

      let title   = currentTitle.trimmingCharacters(in: .whitespacesAndNewlines)
      let linkStr = currentLink.trimmingCharacters(in: .whitespacesAndNewlines)
      let pubDateStr = currentPubDate.trimmingCharacters(in: .whitespacesAndNewlines)

      let formatter = DateFormatter()
      formatter.locale = Locale(identifier: "en_US_POSIX")
      // Try RFC 2822 first (RSS), then ISO8601 (Atom)
      formatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss Z"
      var date = formatter.date(from: pubDateStr)
      if date == nil {
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ssZ"
        date = formatter.date(from: pubDateStr)
      }

      let category = categorize(title: title, description: currentDescription)

      // Extract thumbnail from description if not found in enclosure
      var thumb = currentThumbnailURL
      if thumb.isEmpty {
        thumb = extractFirstImageURL(from: currentDescription) ?? ""
      }

      let thumbnailURL = URL(string: thumb)

      if !title.isEmpty, let url = URL(string: linkStr) {
        parsingArticles.append(ScamArticle(
          title: title,
          link: url,
          pubDate: date ?? Date(),
          source: source.name,
          sourceColor: source.color,
          category: category,
          description: stripHTML(currentDescription).trimmingCharacters(in: .whitespacesAndNewlines),
          thumbnailURL: thumbnailURL
        ))
      }
    }
  }

  // MARK: - Helpers

  private func categorize(title: String, description: String) -> ScamCategory {
    let combined = (title + " " + description).lowercased()
    if combined.contains("phish")                              { return .phishing }
    if combined.contains("romance") || combined.contains("dating") || combined.contains("pig butcher") { return .romance }
    if combined.contains("crypto") || combined.contains("bitcoin") || combined.contains("nft") { return .crypto }
    if combined.contains("invest") || combined.contains("ponzi") || combined.contains("fraud") { return .investment }
    if combined.contains("sms") || combined.contains("text message") || combined.contains("smishing") || combined.contains("otp") { return .sms }
    if combined.contains("ransomware") || combined.contains("malware") || combined.contains("trojan") || combined.contains("spyware") { return .malware }
    if combined.contains("tech support") || combined.contains("microsoft") || combined.contains("apple support") { return .techSupport }
    return .all
  }

  private func stripHTML(_ html: String) -> String {
    guard let data = html.data(using: .utf8) else { return html }
    let options: [NSAttributedString.DocumentReadingOptionKey: Any] = [.documentType: NSAttributedString.DocumentType.html, .characterEncoding: String.Encoding.utf8.rawValue]
    if let attributed = try? NSAttributedString(data: data, options: options, documentAttributes: nil) {
      return attributed.string
    }
    // Fallback: simple regex strip
    return html.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
  }

  private func extractFirstImageURL(from html: String) -> String? {
    // Very naive: find first src="..." in an <img> tag
    let pattern = #"<img[^>]+src\s*=\s*["]([^"]+)["]"#
    guard let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive) else { return nil }
    let range = NSRange(html.startIndex..., in: html)
    if let match = regex.firstMatch(in: html, range: range),
       let captureRange = Range(match.range(at: 1), in: html) {
      return String(html[captureRange])
    }
    return nil
  }
}

// MARK: - ViewModel

@MainActor
final class BlogsViewModel: ObservableObject {
  @Published var articles: [ScamArticle] = []
  @Published var isLoading = false
  @Published var errorMessage: String?

  func fetchArticles(forceRefresh: Bool = false) async {
    guard articles.isEmpty || forceRefresh else { return }

    isLoading = true
    errorMessage = nil

    let ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

    var all: [ScamArticle] = []

    await withTaskGroup(of: [ScamArticle].self) { group in
      for feedSource in RSSFeedSource.all {
        group.addTask {
          guard let url = URL(string: feedSource.url) else { return [] }
          var request = URLRequest(url: url, timeoutInterval: 10)
          request.setValue(ua, forHTTPHeaderField: "User-Agent")
          guard let (data, _) = try? await URLSession.shared.data(for: request) else { return [] }
          return await Task.detached {
            let delegate = RSSParser(source: feedSource)
            let parser = XMLParser(data: data)
            parser.delegate = delegate
            parser.parse()
            return delegate.parsingArticles
          }.value
        }
      }
      for await result in group {
        all.append(contentsOf: result)
      }
    }

    // Sort newest first, deduplicate by title
    var seen = Set<String>()
    let unique = all
      .sorted { $0.pubDate > $1.pubDate }
      .filter { seen.insert($0.title).inserted }

    self.articles = unique
    self.isLoading = false

    if unique.isEmpty {
      errorMessage = "Could not load news feeds. Check your internet connection."
    }
  }
}
