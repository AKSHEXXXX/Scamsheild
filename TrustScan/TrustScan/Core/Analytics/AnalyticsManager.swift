import Foundation
import SwiftUI
import PostHog

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
        config.captureApplicationLifecycleEvents = true // automatically captures app_installed, app_updated, app_opened, app_backgrounded
        
        PostHogSDK.shared.setup(config)
        print("✅ AnalyticsManager: PostHog SDK initialized successfully.")
    }
    
    /// Associates a user with their actions. Call this after a successful login or signup.
    /// - Parameters:
    ///   - userId: The unique identifier for the user.
    ///   - properties: Optional user properties (e.g., plan type, email). Do NOT send PII.
    public func identify(userId: String, properties: [String: Any]? = nil) {
        PostHogSDK.shared.identify(userId, userProperties: properties)
    }
    
    /// Resets the user's identity. Call this on logout to ensure events are no longer associated with them.
    public func reset() {
        PostHogSDK.shared.reset()
    }
    
    /// Captures a custom event.
    /// - Parameters:
    ///   - event: The name of the event.
    ///   - properties: Optional properties associated with the event.
    public func capture(event: String, properties: [String: Any]? = nil) {
        // Safe logging to verify we aren't passing PII accidentally
        #if DEBUG
        print("📊 AnalyticsManager - Tracked Event: \(event) | Properties: \(String(describing: properties))")
        #endif
        
        PostHogSDK.shared.capture(event, userProperties: nil, userPropertiesSetOnce: nil, groupProperties: nil, properties: properties)
    }
    
    /// Tracks a screen view.
    /// - Parameter name: The name of the screen.
    public func screen(name: String) {
        PostHogSDK.shared.screen(name)
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
