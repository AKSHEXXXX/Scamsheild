import SwiftUI
import SafariServices

// MARK: - Main BlogsView

struct BlogsView: View {
  @StateObject private var viewModel = BlogsViewModel()
  @State private var selectedCategory: ScamCategory = .all
  @State private var selectedArticleURL: URL?

  var body: some View {
    ScrollView {
      VStack(spacing: SpacingTokens.large) {

        // Filter Chips
        ScrollView(.horizontal, showsIndicators: false) {
          HStack(spacing: SpacingTokens.small) {
            ForEach(ScamCategory.allCases, id: \.self) { category in
              Button {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                  selectedCategory = category
                }
              } label: {
                HStack(spacing: 4) {
                  Text(categoryEmoji(category))
                    .font(.system(size: 13))
                  Text(category.rawValue)
                    .font(.system(size: 14, weight: .medium))
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(selectedCategory == category ? ColorTokens.acc : ColorTokens.sf)
                .foregroundStyle(selectedCategory == category ? .white : ColorTokens.ik)
                .clipShape(Capsule())
                .overlay(
                  Capsule().stroke(
                    selectedCategory == category ? Color.clear : ColorTokens.st.opacity(0.15),
                    lineWidth: 1
                  )
                )
              }
              .buttonStyle(.plain)
            }
          }
          .padding(.horizontal, SpacingTokens.large)
        }
        .padding(.top, SpacingTokens.small)

        // Source Legend
        if !viewModel.articles.isEmpty {
          ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: SpacingTokens.small) {
              ForEach(RSSFeedSource.all, id: \.name) { src in
                HStack(spacing: 6) {
                  Circle()
                    .fill(Color(hex: src.color) ?? .gray)
                    .frame(width: 8, height: 8)
                  Text(src.name)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(ColorTokens.st)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(ColorTokens.sf)
                .clipShape(Capsule())
              }
            }
            .padding(.horizontal, SpacingTokens.large)
          }
        }

        if viewModel.isLoading {
          VStack(spacing: SpacingTokens.large) {
            ForEach(0..<4) { _ in SkeletonCard() }
          }
          .padding(.horizontal, SpacingTokens.large)

        } else if let error = viewModel.errorMessage {
          VStack(spacing: SpacingTokens.medium) {
            Image(systemName: "wifi.exclamationmark")
              .font(.system(size: 40))
              .foregroundStyle(ColorTokens.st.opacity(0.4))
            Text(error)
              .font(.system(size: 15))
              .foregroundStyle(ColorTokens.st)
              .multilineTextAlignment(.center)
            Button("Try Again") {
              Task { await viewModel.fetchArticles(forceRefresh: true) }
            }
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(ColorTokens.acc)
          }
          .padding(SpacingTokens.large)

        } else if filteredArticles.isEmpty {
          VStack(spacing: SpacingTokens.medium) {
            Text("🔍")
              .font(.system(size: 40))
            Text("No articles yet in this category.\nCheck back soon!")
              .font(.system(size: 15))
              .foregroundStyle(ColorTokens.st)
              .multilineTextAlignment(.center)
          }
          .padding(SpacingTokens.large)

        } else {
          VStack(spacing: SpacingTokens.large) {
            // Featured card (first article)
            if let first = filteredArticles.first {
              Button { selectedArticleURL = first.link } label: {
                FeaturedBlogCard(article: first)
              }
              .buttonStyle(.plain)
              .padding(.horizontal, SpacingTokens.large)

              // Rest of articles
              ForEach(filteredArticles.dropFirst()) { article in
                Button { selectedArticleURL = article.link } label: {
                  BlogCard(article: article)
                }
                .buttonStyle(.plain)
              }
              .padding(.horizontal, SpacingTokens.large)
            }
          }
        }
      }
      .padding(.bottom, SpacingTokens.large)
    }
    .background(ColorTokens.bg.ignoresSafeArea())
    .navigationTitle("Scam Intelligence")
    .refreshable {
      await viewModel.fetchArticles(forceRefresh: true)
    }
    .task {
      await viewModel.fetchArticles()
    }
    .sheet(item: $selectedArticleURL) { url in
      SafariView(url: url).ignoresSafeArea()
    }
  }

  var filteredArticles: [ScamArticle] {
    if selectedCategory == .all {
      return viewModel.articles
    } else {
      return viewModel.articles.filter { $0.category == selectedCategory }
    }
  }

  func categoryEmoji(_ cat: ScamCategory) -> String {
    switch cat {
    case .all:        return "📰"
    case .phishing:   return "🎣"
    case .investment: return "💰"
    case .romance:    return "💔"
    case .techSupport: return "💻"
    case .sms:        return "📱"
    case .crypto:     return "₿"
    case .malware:    return "🦠"
    }
  }
}

extension URL: @retroactive Identifiable {
  public var id: String { self.absoluteString }
}

// MARK: - Featured Card (large, with big thumbnail)

struct FeaturedBlogCard: View {
  let article: ScamArticle

  var body: some View {
    VStack(alignment: .leading, spacing: 0) {
      // Thumbnail or Gradient Banner
      if let thumb = article.thumbnailURL {
        ZStack {
          AsyncImage(url: thumb) { phase in
            switch phase {
            case .success(let img):
              img.resizable()
                .scaledToFill()
                .frame(maxWidth: .infinity)
                .frame(height: 200)
                .clipped()
            default:
              placeholderView(height: 200)
            }
          }

          // Source badge inside image
          VStack {
            HStack {
              Spacer()
              Text(article.source)
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(.white)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(Color(hex: article.sourceColor) ?? ColorTokens.acc)
                .clipShape(Capsule())
                .padding(10)
            }
            Spacer()
          }
        }
      } else {
        // Aesthetic text-only banner
        ZStack(alignment: .bottomLeading) {
          LinearGradient(
            colors: [
              (Color(hex: article.sourceColor) ?? ColorTokens.acc).opacity(0.6),
              (Color(hex: article.sourceColor) ?? ColorTokens.acc).opacity(0.2)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
          )
          .frame(height: 100)

          HStack {
            Image(systemName: "newspaper.fill")
              .font(.system(size: 30))
              .foregroundStyle(.white.opacity(0.8))
              .padding(.bottom, -15)
              .padding(.leading, 20)
            Spacer()
            Text(article.source)
              .font(.system(size: 11, weight: .bold))
              .foregroundStyle(.white)
              .padding(.horizontal, 10)
              .padding(.vertical, 5)
              .background(Color(hex: article.sourceColor) ?? ColorTokens.acc)
              .clipShape(Capsule())
              .padding(10)
          }
        }
        .clipped()
      }

      VStack(alignment: .leading, spacing: SpacingTokens.small) {
        HStack {
          Text(article.category == .all ? "General" : article.category.rawValue)
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(Color(hex: article.sourceColor) ?? ColorTokens.acc)

          Spacer()

          Text(article.relativeDate)
            .font(.caption)
            .foregroundStyle(ColorTokens.st)
        }

        Text(article.title)
          .font(.system(size: 18, weight: .bold))
          .foregroundStyle(ColorTokens.ik)
          .lineLimit(3)
          .multilineTextAlignment(.leading)

        if let desc = article.description, !desc.isEmpty {
          Text(desc)
            .font(.system(size: 13))
            .foregroundStyle(ColorTokens.st)
            .lineLimit(2)
        }
      }
      .padding(SpacingTokens.medium)
    }
    .background(ColorTokens.sf)
    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    .shadow(color: .black.opacity(0.06), radius: 12, y: 6)
  }
}

// MARK: - Regular Blog Card (compact, with side thumbnail)

struct BlogCard: View {
  let article: ScamArticle

  var body: some View {
    if article.thumbnailURL != nil {
      imageLayout
    } else {
      textOnlyLayout
    }
  }

  // MARK: - Image Layout
  private var imageLayout: some View {
    HStack(alignment: .top, spacing: SpacingTokens.medium) {
      ZStack {
        if let thumb = article.thumbnailURL {
          AsyncImage(url: thumb) { phase in
            switch phase {
            case .success(let img):
              img.resizable()
                .scaledToFill()
                .frame(width: 90, height: 90)
                .clipped()
            default:
              placeholderView(width: 90, height: 90)
            }
          }
        }
      }
      .frame(width: 90, height: 90)
      .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

      VStack(alignment: .leading, spacing: 4) {
        HStack {
          Text(article.source)
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(Color(hex: article.sourceColor) ?? ColorTokens.acc)
          Spacer()
          Text(article.relativeDate)
            .font(.system(size: 10))
            .foregroundStyle(ColorTokens.st)
        }

        Text(article.title)
          .font(.system(size: 14, weight: .semibold))
          .foregroundStyle(ColorTokens.ik)
          .lineLimit(3)
          .multilineTextAlignment(.leading)

        Text(article.category == .all ? "General" : article.category.rawValue)
          .font(.system(size: 11, weight: .medium))
          .padding(.horizontal, 8)
          .padding(.vertical, 3)
          .background(ColorTokens.st.opacity(0.1))
          .foregroundStyle(ColorTokens.st)
          .clipShape(Capsule())
      }
    }
    .padding(SpacingTokens.medium)
    .background(ColorTokens.sf)
    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    .shadow(color: .black.opacity(0.04), radius: 8, y: 4)
  }

  // MARK: - Text Only Layout
  private var textOnlyLayout: some View {
    VStack(alignment: .leading, spacing: 10) {
      HStack {
        Text(article.source)
          .font(.system(size: 11, weight: .bold))
          .foregroundStyle(Color(hex: article.sourceColor) ?? ColorTokens.acc)
        Spacer()
        Text(article.relativeDate)
          .font(.system(size: 11))
          .foregroundStyle(ColorTokens.st)
      }

      Text(article.title)
        .font(.system(size: 15, weight: .bold))
        .foregroundStyle(ColorTokens.ik)
        .lineLimit(3)
        .multilineTextAlignment(.leading)
        .fixedSize(horizontal: false, vertical: true)

      if let desc = article.description, !desc.isEmpty {
        Text(desc)
          .font(.system(size: 13))
          .foregroundStyle(ColorTokens.st)
          .lineLimit(2)
          .multilineTextAlignment(.leading)
      }

      HStack {
        Text(article.category == .all ? "General" : article.category.rawValue)
          .font(.system(size: 11, weight: .medium))
          .padding(.horizontal, 8)
          .padding(.vertical, 4)
          .background(ColorTokens.st.opacity(0.1))
          .foregroundStyle(ColorTokens.st)
          .clipShape(Capsule())
        
        Spacer()
        
        Image(systemName: "arrow.up.right.circle.fill")
          .font(.system(size: 20))
          .foregroundStyle(ColorTokens.st.opacity(0.3))
      }
    }
    .padding(SpacingTokens.large)
    .background(ColorTokens.sf)
    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    .overlay(
      RoundedRectangle(cornerRadius: 16, style: .continuous)
        .stroke(
          LinearGradient(
            colors: [(Color(hex: article.sourceColor) ?? ColorTokens.acc).opacity(0.4), .clear],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
          ),
          lineWidth: 1
        )
    )
    .shadow(color: .black.opacity(0.03), radius: 10, y: 5)
  }
}

// MARK: - Placeholder view helper

private func placeholderView(width: CGFloat? = nil, height: CGFloat) -> some View {
  ZStack {
    Rectangle()
      .fill(LinearGradient(
        colors: [Color(.systemGray5), Color(.systemGray6)],
        startPoint: .topLeading, endPoint: .bottomTrailing
      ))
    Image(systemName: "newspaper.fill")
      .font(.system(size: height > 100 ? 40 : 24))
      .foregroundStyle(Color(.systemGray3))
  }
  .frame(width: width, height: height)
}

// MARK: - SafariView

struct SafariView: UIViewControllerRepresentable {
  let url: URL
  func makeUIViewController(context: Context) -> SFSafariViewController {
    SFSafariViewController(url: url)
  }
  func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}

// MARK: - Shimmer Skeleton

struct SkeletonCard: View {
  @State private var shimmer = false

  var body: some View {
    HStack(alignment: .top, spacing: SpacingTokens.medium) {
      RoundedRectangle(cornerRadius: 12)
        .fill(shimmerGradient)
        .frame(width: 90, height: 90)

      VStack(alignment: .leading, spacing: 8) {
        RoundedRectangle(cornerRadius: 4)
          .fill(shimmerGradient)
          .frame(height: 12)
        RoundedRectangle(cornerRadius: 4)
          .fill(shimmerGradient)
          .frame(height: 12)
        RoundedRectangle(cornerRadius: 4)
          .fill(shimmerGradient)
          .frame(width: 80, height: 12)
      }
      .padding(.top, 4)

      Spacer()
    }
    .padding(SpacingTokens.medium)
    .background(ColorTokens.sf)
    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    .onAppear {
      withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
        shimmer = true
      }
    }
  }

  var shimmerGradient: LinearGradient {
    LinearGradient(
      colors: [ColorTokens.st.opacity(0.08), ColorTokens.st.opacity(0.18), ColorTokens.st.opacity(0.08)],
      startPoint: shimmer ? .trailing : .leading,
      endPoint: shimmer ? .leading : .trailing
    )
  }
}

// MARK: - Color hex extension

extension Color {
  init?(hex: String) {
    var hexSanitized = hex.trimmingCharacters(in: .whitespacesAndNewlines)
    hexSanitized = hexSanitized.hasPrefix("#") ? String(hexSanitized.dropFirst()) : hexSanitized
    guard hexSanitized.count == 6, let intVal = UInt64(hexSanitized, radix: 16) else { return nil }
    let r = Double((intVal & 0xFF0000) >> 16) / 255
    let g = Double((intVal & 0x00FF00) >> 8)  / 255
    let b = Double(intVal & 0x0000FF)          / 255
    self.init(red: r, green: g, blue: b)
  }
}
