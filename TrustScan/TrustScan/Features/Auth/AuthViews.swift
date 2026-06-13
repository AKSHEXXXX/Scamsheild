import SwiftUI
import AuthenticationServices

struct LoginView: View {
  @ObservedObject var viewModel: AuthViewModel
  @Environment(\.openURL) private var openURL
  @State private var isPasswordVisible = false

  var body: some View {
    GeometryReader { proxy in
      ScrollView {
        VStack(spacing: SpacingTokens.medium) {
          Spacer()

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

          Spacer().frame(height: SpacingTokens.small)

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

            HStack {
              if isPasswordVisible {
                TextField("Password", text: $viewModel.password)
                  .textContentType(.password)
                  .autocapitalization(.none)
                  .disableAutocorrection(true)
              } else {
                SecureField("Password", text: $viewModel.password)
                  .textContentType(.password)
              }
              Button(action: { isPasswordVisible.toggle() }) {
                Image(systemName: isPasswordVisible ? "eye.slash.fill" : "eye.fill")
                  .foregroundStyle(ColorTokens.st)
              }
            }
            .padding()
            .background(ColorTokens.sf)
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .accessibilityLabel("Password")

            HStack {
              Spacer()
              Button("Forgot Password?") {
                // TODO: Implement forgot password
              }
              .font(.system(size: 13, weight: .medium))
              .foregroundStyle(ColorTokens.acc)
            }
            .padding(.top, 4)
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
                .frame(maxWidth: .infinity, minHeight: 48)
            } else {
              Text("Sign In")
                .font(TypographyTokens.sectionTitle)
                .frame(maxWidth: .infinity, minHeight: 48)
            }
          }
          .buttonStyle(.plain)
          .foregroundStyle(.white)
          .background(ColorTokens.acc)
          .clipShape(RoundedRectangle(cornerRadius: 16))
          .disabled(viewModel.isLoading)

          // Divider
          HStack {
            Rectangle().fill(ColorTokens.st.opacity(0.3)).frame(height: 1)
            Text("or")
              .font(TypographyTokens.caption)
              .foregroundStyle(ColorTokens.st)
            Rectangle().fill(ColorTokens.st.opacity(0.3)).frame(height: 1)
          }

          // OAuth Buttons
          VStack(spacing: SpacingTokens.medium) {
            Button {
              if let url = viewModel.authService.oAuthURL(provider: "apple") {
                openURL(url)
              }
            } label: {
              HStack {
                Image(systemName: "applelogo")
                  .frame(width: 20, height: 20)
                Text("Continue with Apple")
                  .font(.system(size: 16, weight: .semibold))
              }
              .frame(maxWidth: .infinity, minHeight: 48)
            }
            .buttonStyle(.plain)
            .foregroundStyle(ColorTokens.ik)
            .background(ColorTokens.sf)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(ColorTokens.st.opacity(0.3), lineWidth: 1.5))

            Button {
              if let url = viewModel.authService.oAuthURL(provider: "google") {
                openURL(url)
              }
            } label: {
              HStack {
                Image("google_g_logo")
                  .resizable()
                  .scaledToFit()
                  .frame(width: 20, height: 20)
                Text("Continue with Google")
                  .font(.system(size: 16, weight: .semibold))
              }
              .frame(maxWidth: .infinity, minHeight: 48)
            }
            .buttonStyle(.plain)
            .foregroundStyle(ColorTokens.ik)
            .background(ColorTokens.sf)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(ColorTokens.st.opacity(0.3), lineWidth: 1.5))

            // Biometric Login Button
            Button {
              Task { await viewModel.authenticateWithBiometrics() }
            } label: {
              Label("Sign in with Face ID", systemImage: "faceid")
                .font(.system(size: 16, weight: .semibold))
                .frame(maxWidth: .infinity, minHeight: 48)
            }
            .buttonStyle(.plain)
            .foregroundStyle(ColorTokens.acc)
            .background(ColorTokens.sf)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(ColorTokens.acc.opacity(0.4), lineWidth: 1.5))
          }

          // Create Account Link
          Button {
            viewModel.isShowingSignUp = true
            viewModel.errorMessage = nil
          } label: {
            Text("Don't have an account? **Create one**")
              .font(TypographyTokens.body)
              .foregroundStyle(ColorTokens.acc)
          }

          Spacer()
        }
        .padding(.horizontal, SpacingTokens.large)
        .padding(.vertical, SpacingTokens.large)
        .frame(minHeight: proxy.size.height)
      }
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
