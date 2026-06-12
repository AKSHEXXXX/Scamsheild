import SwiftUI

struct SettingsView: View {
  @ObservedObject var viewModel: SettingsViewModel
  @Binding var hasCompletedOnboarding: Bool
  let onHistoryChanged: () -> Void
  let onSignOut: () -> Void

  @State private var isShowingClearConfirmation = false

  var body: some View {
    Form {
      Section("Account") {
        Button("Sign Out", role: .destructive) {
          onSignOut()
        }
      }

      Section("Local Data") {
        LabeledContent("Saved scans", value: "\(viewModel.storedScanCount)")

        Button("Delete all local history", role: .destructive) {
          isShowingClearConfirmation = true
        }
      }

      Section("Privacy & Data") {
        NavigationLink("Privacy Policy & Data Handling") {
          PrivacyPolicyView()
        }
      }

      Section("Permissions") {
        HStack {
          Text("Photo Library")
          Spacer()
          Text(permissionStatusText(PhotoPermissionManager.currentStatus))
            .foregroundStyle(ColorTokens.st)
        }
        .onTapGesture { openAppSettings() }

        HStack {
          Text("Camera")
          Spacer()
          Text(permissionStatusText(CameraPermissionManager.currentStatus))
            .foregroundStyle(ColorTokens.st)
        }
        .onTapGesture { openAppSettings() }
      }

      Section("Experience") {
        Button("Replay onboarding") {
          hasCompletedOnboarding = false
        }
      }

      Section("About") {
        LabeledContent("Version", value: "1.0 (1)")
      }

      if let lastOperationError = viewModel.lastOperationError {
        Section("Issues") {
          Text(lastOperationError)
            .foregroundStyle(ColorTokens.dng)
        }
      }
    }
    .navigationTitle("Settings")
    .task { await viewModel.refresh() }
    .alert("Delete local history?", isPresented: $isShowingClearConfirmation) {
      Button("Delete", role: .destructive) {
        Task {
          await viewModel.clearHistory()
          onHistoryChanged()
        }
      }
      Button("Cancel", role: .cancel) {}
    } message: {
      Text("This removes saved scan results from this device.")
    }
  }

  private func permissionStatusText(_ status: PermissionStatus) -> String {
    switch status {
    case .authorized: return "Granted"
    case .limited: return "Limited"
    case .denied: return "Denied"
    case .restricted: return "Restricted"
    case .notDetermined: return "Not Set"
    }
  }

  private func openAppSettings() {
    guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
    UIApplication.shared.open(url)
  }
}

// MARK: - Privacy Policy View (S-13)

struct PrivacyPolicyView: View {
  @State private var expandedSections: Set<String> = []

  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: SpacingTokens.large) {
        privacySection(
          id: "collect",
          title: "What we collect",
          icon: "doc.text.magnifyingglass",
          content: "When you submit a screenshot for analysis, we transmit the image to our analysis server. We also generate an anonymous session identifier to correlate your scans — this is not tied to your identity or device ID."
        )

        privacySection(
          id: "images",
          title: "What we do with your images",
          icon: "photo.badge.checkmark",
          content: "Your images are processed solely for scam analysis. They are not stored permanently on our servers, not used for machine learning training, and not shared with any third party. Images are deleted from our processing pipeline once analysis is complete."
        )

        privacySection(
          id: "retention",
          title: "How long we keep data",
          icon: "clock.arrow.circlepath",
          content: "Images: Deleted immediately after analysis completes. Analysis results: Retained on our servers for a limited period to support result retrieval. Local history on your device: Stored until you delete it."
        )

        privacySection(
          id: "never",
          title: "What we never do",
          icon: "hand.raised.slash",
          content: "We never sell your data. We never share your data with advertisers. We never link your scans to your personal identity. We never use third-party advertising SDKs. We never access your photo library without your explicit action."
        )

        Divider()
          .padding(.vertical, SpacingTokens.medium)

        Text("TrustScan is committed to transparency. If you have questions about our data practices, contact us at privacy@trustscan.app.")
          .font(TypographyTokens.caption)
          .foregroundStyle(ColorTokens.st)
      }
      .padding(SpacingTokens.large)
    }
    .background(ColorTokens.bg.ignoresSafeArea())
    .navigationTitle("Privacy & Data")
    .navigationBarTitleDisplayMode(.inline)
  }

  private func privacySection(id: String, title: String, icon: String, content: String) -> some View {
    VStack(alignment: .leading, spacing: SpacingTokens.small) {
      Button {
        withAnimation(.easeInOut(duration: 0.25)) {
          if expandedSections.contains(id) {
            expandedSections.remove(id)
          } else {
            expandedSections.insert(id)
          }
        }
      } label: {
        HStack {
          Image(systemName: icon)
            .foregroundStyle(ColorTokens.acc)
            .frame(width: 30)

          Text(title)
            .font(TypographyTokens.sectionTitle)
            .foregroundStyle(ColorTokens.ik)

          Spacer()

          Image(systemName: expandedSections.contains(id) ? "chevron.up" : "chevron.down")
            .foregroundStyle(ColorTokens.st)
        }
      }
      .buttonStyle(.plain)

      if expandedSections.contains(id) {
        Text(content)
          .font(TypographyTokens.body)
          .foregroundStyle(ColorTokens.st)
          .padding(.leading, 42)
          .transition(.opacity.combined(with: .move(edge: .top)))
      }
    }
    .padding(SpacingTokens.medium)
    .background(
      RoundedRectangle(cornerRadius: 20, style: .continuous)
        .fill(ColorTokens.sf)
    )
  }
}
