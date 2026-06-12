import SwiftUI
import AuthenticationServices

struct LoginView: View {
  @ObservedObject var viewModel: AuthViewModel
  @Environment(\.openURL) private var openURL

  var body: some View {
    ScrollView {
      VStack(spacing: SpacingTokens.large) {
        Spacer(minLength: SpacingTokens.xLarge)

        // Logo / Branding
        VStack(spacing: SpacingTokens.medium) {
          Image(systemName: "shield.checkered")
            .font(.system(size: 72, weight: .bold))
            .foregroundStyle(ColorTokens.acc)

          Text("TrustScan")
            .font(.system(size: 40, weight: .bold, design: .rounded))
            .foregroundStyle(ColorTokens.ik)

          Text("Scan suspicious messages before they cost you.")
            .font(TypographyTokens.body)
            .foregroundStyle(ColorTokens.st)
            .multilineTextAlignment(.center)
        }

        Spacer(minLength: SpacingTokens.medium)

        // Sign In Form
        VStack(spacing: SpacingTokens.medium) {
          TextField("Email", text: $viewModel.email)
            .textContentType(.emailAddress)
            .keyboardType(.emailAddress)
            .autocapitalization(.none)
            .disableAutocorrection(true)
            .padding()
            .background(ColorTokens.sf)
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .accessibilityLabel("Email address")

          SecureField("Password", text: $viewModel.password)
            .textContentType(.password)
            .padding()
            .background(ColorTokens.sf)
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .accessibilityLabel("Password")
        }

        // Error Message
        if let error = viewModel.errorMessage {
          Text(error)
            .font(TypographyTokens.caption)
            .foregroundStyle(ColorTokens.dng)
            .multilineTextAlignment(.center)
        }

        // Success Message (after sign up)
        if let success = viewModel.signUpSuccessMessage {
          Text(success)
            .font(TypographyTokens.caption)
            .foregroundStyle(ColorTokens.sfe)
            .multilineTextAlignment(.center)
        }

        // Sign In Button
        Button {
          Task { await viewModel.signIn() }
        } label: {
          if viewModel.isLoading {
            ProgressView()
              .tint(.white)
              .frame(maxWidth: .infinity)
          } else {
            Text("Sign In")
              .font(TypographyTokens.sectionTitle)
              .frame(maxWidth: .infinity)
          }
        }
        .buttonStyle(.borderedProminent)
        .tint(ColorTokens.acc)
        .disabled(viewModel.isLoading)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

        // Divider
        HStack {
          Rectangle().fill(ColorTokens.st.opacity(0.3)).frame(height: 1)
          Text("or")
            .font(TypographyTokens.caption)
            .foregroundStyle(ColorTokens.st)
          Rectangle().fill(ColorTokens.st.opacity(0.3)).frame(height: 1)
        }

        // OAuth Buttons
        Button {
          if let url = viewModel.authService.oAuthURL(provider: "apple") {
            openURL(url)
          }
        } label: {
          Label("Continue with Apple", systemImage: "applelogo")
            .font(TypographyTokens.body)
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered)
        .tint(ColorTokens.ik)

        Button {
          if let url = viewModel.authService.oAuthURL(provider: "google") {
            openURL(url)
          }
        } label: {
          Label("Continue with Google", systemImage: "globe")
            .font(TypographyTokens.body)
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered)

        // Create Account Link
        Button {
          viewModel.isShowingSignUp = true
          viewModel.errorMessage = nil
        } label: {
          Text("Don't have an account? **Create one**")
            .font(TypographyTokens.body)
            .foregroundStyle(ColorTokens.acc)
        }

        Spacer(minLength: SpacingTokens.large)
      }
      .padding(.horizontal, SpacingTokens.large)
    }
    .background(
      LinearGradient(
        colors: [ColorTokens.bg, ColorTokens.sfm],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
      )
      .ignoresSafeArea()
    )
    .sheet(isPresented: $viewModel.isShowingSignUp) {
      SignUpView(viewModel: viewModel)
    }
  }
}

struct SignUpView: View {
  @ObservedObject var viewModel: AuthViewModel
  @Environment(\.dismiss) private var dismiss

  var body: some View {
    NavigationStack {
      ScrollView {
        VStack(spacing: SpacingTokens.large) {
          Spacer(minLength: SpacingTokens.xLarge)

          Image(systemName: "person.badge.plus")
            .font(.system(size: 54, weight: .semibold))
            .foregroundStyle(ColorTokens.acc)

          Text("Create Account")
            .font(TypographyTokens.hero)
            .foregroundStyle(ColorTokens.ik)

          VStack(spacing: SpacingTokens.medium) {
            TextField("Email", text: $viewModel.email)
              .textContentType(.emailAddress)
              .keyboardType(.emailAddress)
              .autocapitalization(.none)
              .disableAutocorrection(true)
              .padding()
              .background(ColorTokens.sf)
              .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

            SecureField("Password", text: $viewModel.password)
              .textContentType(.newPassword)
              .padding()
              .background(ColorTokens.sf)
              .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

            SecureField("Confirm Password", text: $viewModel.confirmPassword)
              .textContentType(.newPassword)
              .padding()
              .background(ColorTokens.sf)
              .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
          }

          if let error = viewModel.errorMessage {
            Text(error)
              .font(TypographyTokens.caption)
              .foregroundStyle(ColorTokens.dng)
              .multilineTextAlignment(.center)
          }

          Button {
            Task { await viewModel.signUp() }
          } label: {
            if viewModel.isLoading {
              ProgressView().tint(.white).frame(maxWidth: .infinity)
            } else {
              Text("Create Account")
                .font(TypographyTokens.sectionTitle)
                .frame(maxWidth: .infinity)
            }
          }
          .buttonStyle(.borderedProminent)
          .tint(ColorTokens.acc)
          .disabled(viewModel.isLoading)

          Spacer()
        }
        .padding(.horizontal, SpacingTokens.large)
      }
      .background(ColorTokens.bg.ignoresSafeArea())
      .navigationBarTitleDisplayMode(.inline)
      .toolbar {
        ToolbarItem(placement: .cancellationAction) {
          Button("Cancel") { dismiss() }
        }
      }
    }
  }
}
