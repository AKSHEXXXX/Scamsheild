import Foundation

struct ScamArticle: Identifiable, Equatable {
  let id = UUID()
  let title: String
  let link: URL
  let pubDate: Date
  let source: String
  let category: ScamCategory
  let description: String?
  
  var relativeDate: String {
    let formatter = RelativeDateTimeFormatter()
    formatter.unitsStyle = .abbreviated
    return formatter.localizedString(for: pubDate, relativeTo: Date())
  }
}

enum ScamCategory: String, CaseIterable {
  case all = "All"
  case phishing = "Phishing"
  case investment = "Investment"
  case romance = "Romance Scam"
  case techSupport = "Tech Support"
  case sms = "SMS / OTP"
  case crypto = "Crypto"
}

class FTCRSSParser: NSObject, XMLParserDelegate {
  private var currentElement = ""
  private var currentTitle = ""
  private var currentLink = ""
  private var currentPubDate = ""
  private var currentDescription = ""
  var parsingArticles: [ScamArticle] = []
  
  func parser(_ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?, qualifiedName qName: String?, attributes attributeDict: [String : String] = [:]) {
    currentElement = elementName
    if elementName == "item" {
      currentTitle = ""
      currentLink = ""
      currentPubDate = ""
      currentDescription = ""
    }
  }
  
  func parser(_ parser: XMLParser, foundCharacters string: String) {
    switch currentElement {
    case "title": currentTitle += string
    case "link": currentLink += string
    case "pubDate": currentPubDate += string
    case "description": currentDescription += string
    default: break
    }
  }
  
  func parser(_ parser: XMLParser, didEndElement elementName: String, namespaceURI: String?, qualifiedName qName: String?) {
    if elementName == "item" {
      let title = currentTitle.trimmingCharacters(in: .whitespacesAndNewlines)
      let linkStr = currentLink.trimmingCharacters(in: .whitespacesAndNewlines)
      let pubDateStr = currentPubDate.trimmingCharacters(in: .whitespacesAndNewlines)
      
      let formatter = DateFormatter()
      formatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss Z"
      formatter.locale = Locale(identifier: "en_US_POSIX")
      let date = formatter.date(from: pubDateStr) ?? Date()
      
      // Naive category logic
      var category: ScamCategory = .all
      let lowerTitle = title.lowercased()
      if lowerTitle.contains("phish") { category = .phishing }
      else if lowerTitle.contains("invest") { category = .investment }
      else if lowerTitle.contains("crypto") { category = .crypto }
      else if lowerTitle.contains("romance") { category = .romance }
      else if lowerTitle.contains("tech") { category = .techSupport }
      else if lowerTitle.contains("text") || lowerTitle.contains("sms") { category = .sms }
      
      if let url = URL(string: linkStr) {
        let article = ScamArticle(
          title: title,
          link: url,
          pubDate: date,
          source: "FTC",
          category: category,
          description: currentDescription.trimmingCharacters(in: .whitespacesAndNewlines)
        )
        parsingArticles.append(article)
      }
    }
  }
}

@MainActor
final class BlogsViewModel: ObservableObject {
  @Published var articles: [ScamArticle] = []
  @Published var isLoading = false
  @Published var errorMessage: String?
  
  func fetchArticles() async {
    guard articles.isEmpty else { return } // Basic caching
    
    isLoading = true
    errorMessage = nil
    
    guard let url = URL(string: "https://www.ftc.gov/rss/alerts") else { return }
    
    do {
      let (data, _) = try await URLSession.shared.data(from: url)
      
      // Parse synchronously off the main thread
      let articles = await Task.detached {
        let parserDelegate = FTCRSSParser()
        let parser = XMLParser(data: data)
        parser.delegate = parserDelegate
        parser.parse()
        return parserDelegate.parsingArticles
      }.value
      
      self.articles = articles
      self.isLoading = false
    } catch {
      errorMessage = "Failed to load scam intelligence feed."
      isLoading = false
    }
  }
}
