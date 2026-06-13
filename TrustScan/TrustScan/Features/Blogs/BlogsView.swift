import SwiftUI
import SafariServices

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
                selectedCategory = category
              } label: {
                Text(category.rawValue)
                  .font(.system(size: 14, weight: .medium))
                  .padding(.horizontal, 16)
                  .padding(.vertical, 8)
                  .background(selectedCategory == category ? ColorTokens.acc : ColorTokens.sf)
                  .foregroundStyle(selectedCategory == category ? .white : ColorTokens.ik)
                  .clipShape(Capsule())
              }
            }
          }
          .padding(.horizontal, SpacingTokens.large)
        }
        .padding(.top, SpacingTokens.small)
        
        if viewModel.isLoading {
          VStack(spacing: SpacingTokens.large) {
            ForEach(0..<4) { _ in
              SkeletonCard()
            }
          }
          .padding(.horizontal, SpacingTokens.large)
        } else if let errorMessage = viewModel.errorMessage {
          Text(errorMessage)
            .foregroundStyle(ColorTokens.dng)
            .padding()
        } else {
          VStack(spacing: SpacingTokens.large) {
            ForEach(filteredArticles) { article in
              Button {
                selectedArticleURL = article.link
              } label: {
                BlogCard(article: article)
              }
              .buttonStyle(.plain)
            }
          }
          .padding(.horizontal, SpacingTokens.large)
        }
      }
      .padding(.bottom, SpacingTokens.large)
    }
    .background(ColorTokens.bg.ignoresSafeArea())
    .navigationTitle("Scam Intelligence")
    .task {
      await viewModel.fetchArticles()
    }
    .sheet(item: $selectedArticleURL) { url in
      SafariView(url: url)
        .ignoresSafeArea()
    }
  }
  
  var filteredArticles: [ScamArticle] {
    if selectedCategory == .all {
      return viewModel.articles
    } else {
      return viewModel.articles.filter { $0.category == selectedCategory }
    }
  }
}

extension URL: @retroactive Identifiable {
  public var id: String { self.absoluteString }
}

struct SafariView: UIViewControllerRepresentable {
  let url: URL
  
  func makeUIViewController(context: Context) -> SFSafariViewController {
    SFSafariViewController(url: url)
  }
  
  func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}

struct BlogCard: View {
  let article: ScamArticle
  
  var body: some View {
    VStack(alignment: .leading, spacing: 0) {
      // Placeholder since we don't have images in FTC RSS
      ZStack {
        Rectangle()
          .fill(ColorTokens.st.opacity(0.1))
        
        Image(systemName: "newspaper.fill")
          .font(.system(size: 48))
          .foregroundStyle(ColorTokens.st.opacity(0.3))
      }
      .frame(height: 140)
      
      VStack(alignment: .leading, spacing: SpacingTokens.small) {
        HStack {
          Text(article.source)
            .font(.caption)
            .fontWeight(.semibold)
            .foregroundStyle(ColorTokens.acc)
          
          Spacer()
          
          Text(article.relativeDate)
            .font(.caption)
            .foregroundStyle(ColorTokens.st)
        }
        
        Text(article.title)
          .font(.system(size: 16, weight: .semibold))
          .foregroundStyle(ColorTokens.ik)
          .lineLimit(2)
          .multilineTextAlignment(.leading)
        
        Text(article.category.rawValue)
          .font(.system(size: 12, weight: .medium))
          .padding(.horizontal, 8)
          .padding(.vertical, 4)
          .background(ColorTokens.st.opacity(0.1))
          .foregroundStyle(ColorTokens.st)
          .clipShape(Capsule())
      }
      .padding(SpacingTokens.medium)
    }
    .background(ColorTokens.sf)
    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    .shadow(color: .black.opacity(0.04), radius: 8, y: 4)
  }
}

struct SkeletonCard: View {
  @State private var shimmer = false
  
  var body: some View {
    VStack(alignment: .leading, spacing: 8) {
      Rectangle()
        .fill(shimmerGradient)
        .frame(height: 140)
      
      VStack(alignment: .leading, spacing: 8) {
        Rectangle()
          .fill(shimmerGradient)
          .frame(height: 14)
          .cornerRadius(4)
        Rectangle()
          .fill(shimmerGradient)
          .frame(height: 14)
          .frame(maxWidth: .infinity * 0.7)
          .cornerRadius(4)
      }
      .padding(SpacingTokens.medium)
    }
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
      colors: [ColorTokens.st.opacity(0.1), ColorTokens.st.opacity(0.2), ColorTokens.st.opacity(0.1)],
      startPoint: shimmer ? .trailing : .leading,
      endPoint: shimmer ? .leading : .trailing
    )
  }
}
