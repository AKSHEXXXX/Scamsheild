import Foundation
import SwiftUI
import PostHog
import UIKit

/// Centralized manager for all analytics tracking.
/// Wraps the official PostHog iOS SDK to decouple the rest of the app from it,
/// ensuring that tracking calls are safe, non-blocking, and easy to maintain.
public final class AnalyticsManager {
    public static let shared = AnalyticsManager()
    
    private init() {}
    
    /// Initializes the PostHog SDK. Call this as early as possible (e.g., in `App.init` or `AppDelegate`).
    public func setup() {
        let apiKey = APIEnvironment.posthogAPIKey
        let host = APIEnvironment.posthogHost
        
        guard !apiKey.isEmpty else {
            print("⚠️ AnalyticsManager: Missing POSTHOG_API_KEY. Analytics will be disabled.")
            return
        }
        
        let config = PostHogConfig(apiKey: apiKey, host: host)
        config.captureApplicationLifecycleEvents = true
        
        // ── Session replay ────────────────────────────────────────────────────
        config.sessionReplay = true
        // Mask all text input fields by default to avoid capturing sensitive data
        // Individual views can override with .posthogMask() / .posthogUnmask()
        config.sessionReplayConfig.maskAllTextInputs = true
        config.sessionReplayConfig.maskAllImages = false
        config.sessionReplayConfig.captureNetworkTelemetry = false

        // ── Surveys (NPS, feedback, feature polls) ─────────────────────────────
        config.enableSurveysAndEarlyAccessFeatures = true

        // ── Exception autocapture (Error Tracking) ──────────────────────────────
        // Captures Mach exceptions, POSIX signals, and uncaught NSExceptions as
        // $exception events (fatal crashes are persisted and sent on next launch).
        config.errorTrackingConfig.autoCapture = true

        PostHogSDK.shared.setup(config)
        print("✅ AnalyticsManager: PostHog SDK initialized successfully.")
    }
    
    /// Associates a user with their actions. Call this after a successful login or signup.
    public func identify(userId: String, properties: [String: Any]? = nil) {
        PostHogSDK.shared.identify(userId, userProperties: properties)
    }
    
    /// Resets the user's identity. Call this on logout to ensure events are no longer associated with them.
    public func reset() {
        PostHogSDK.shared.reset()
    }
    
    /// Captures a custom event.
    public func capture(event: String, properties: [String: Any]? = nil) {
        #if DEBUG
        print("📊 AnalyticsManager - Tracked Event: \(event) | Properties: \(String(describing: properties))")
        #endif
        PostHogSDK.shared.capture(event, properties: properties)
    }
    
    /// Tracks a screen view.
    public func screen(name: String) {
        PostHogSDK.shared.screen(name)
    }
    
    // ── Exception capture (Error Tracking) ────────────────────────────────────
    
    /// Manually captures a thrown error as a `$exception` event. Use this inside
    /// `catch` blocks for errors you want tracked but can recover from.
    public func captureException(_ error: Error) {
        PostHogSDK.shared.captureException(error)
    }
    
    // ── Feature Flags ─────────────────────────────────────────────────────────
    
    /// Returns true if the given feature flag is enabled for the current user.
    public func isFeatureEnabled(_ key: String) -> Bool {
        PostHogSDK.shared.isFeatureEnabled(key)
    }
    
    /// Returns the payload value for a feature flag (string, number, or JSON).
    public func featureFlagPayload(_ key: String) -> Any? {
        PostHogSDK.shared.getFeatureFlagPayload(key)
    }
    
    /// Reloads feature flags from the PostHog server. Call this after login
    /// to ensure flags are evaluated against the new user identity.
    public func reloadFeatureFlags() {
        PostHogSDK.shared.reloadFeatureFlags()
    }
    
    /// Registers a reload callback so the app can react to flag changes.
    /// The closure is called on the main thread whenever flags are refreshed.
    public func onFeatureFlags(_ callback: @escaping () -> Void) {
        PostHogSDK.shared.onFeatureFlags(callback)
    }
}

// MARK: - View Modifiers

public struct TrackScreenViewModifier: ViewModifier {
    let screenName: String
    
    public func body(content: Content) -> some View {
        content
            .onAppear {
                AnalyticsManager.shared.screen(name: screenName)
            }
    }
}

public extension View {
    /// Modifier to automatically track when a screen appears.
    func trackScreen(name: String) -> some View {
        modifier(TrackScreenViewModifier(screenName: name))
    }
}
