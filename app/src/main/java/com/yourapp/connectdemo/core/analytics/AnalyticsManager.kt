package com.yourapp.connectdemo.core.analytics

import android.app.Application
import android.content.Context
import androidx.annotation.Keep
import com.posthog.PostHog
import com.posthog.PostHogConfig
import com.posthog.PostHogInterface
import javax.inject.Inject
import javax.inject.Singleton

@Keep
@Singleton
class AnalyticsManager @Inject constructor(
    private val application: Application
) {

    // ──────────────────────────────────────────────────────────────────────────
    // Constants matching iOS PostHog event/property names exactly
    // ──────────────────────────────────────────────────────────────────────────
    companion object {
        const val PROP_PLATFORM = "platform"
        const val PROP_CHANNEL = "channel"
        const val PROP_VERDICT = "verdict"
        const val PROP_SCORE = "score"
        const val PROP_SCAN_ID = "scan_id"
        const val PROP_METHOD = "method"
        const val PROP_ERROR = "error"
        const val PROP_ACTION = "action"
        const val PROP_SCREEN_NAME = "screen_name"

        // iOS scan channels
        const val CHANNEL_IMAGE = "image"
        const val CHANNEL_QR = "qr"
        const val CHANNEL_TEXT = "text"
        const val CHANNEL_SMS = "sms"
        const val CHANNEL_UPLOAD = "upload"
    }

    private val posthog: PostHogInterface by lazy {
        val apiKey = BuildConfig.POSTHOG_API_KEY
        val host = BuildConfig.POSTHOG_HOST

        if (apiKey.isEmpty() || apiKey.startsWith("YOUR_")) {
            throw IllegalStateException(
                "PostHog API key not configured. Set POSTHOG_API_KEY in build.gradle.kts"
            )
        }

        PostHog.Builder(application, apiKey, host)
            // ── Session Replay ─────────────────────────────────────────────────
            .captureScreenViews(true)
            .sessionReplay(true)
            .sessionReplayConfig { config ->
                config.maskAllTextInputs = true
                config.maskAllImages = false
            }
            // ── Surveys (NPS, feedback, feature polls) ──────────────────────────
            .enableSurveys(true)
            // ── Error Tracking (autocapture crashes/ANRs) ────────────────────────
            .errorTrackingConfig { config ->
                config.autoCapture = true
            }
            // ── Feature Flags ───────────────────────────────────────────────────
            .build()
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Public API — mirrors iOS AnalyticsManager method signatures
    // ──────────────────────────────────────────────────────────────────────────

    /** Associates a user with their actions. Call after successful login/signup. */
    fun identify(distinctId: String, properties: Map<String, Any>? = null) {
        val props = properties?.toMutableMap() ?: mutableMapOf()
        props[PROP_PLATFORM] = "android"
        posthog.identify(distinctId, props)
    }

    /** Resets the user's identity. Call on logout. */
    fun reset() {
        posthog.reset()
    }

    /** Captures a custom event with platform property auto-added. */
    fun capture(event: String, properties: Map<String, Any>? = null) {
        val props = properties?.toMutableMap() ?: mutableMapOf()
        props[PROP_PLATFORM] = "android"
        posthog.capture(event, props)
    }

    /** Tracks a screen view with platform property auto-added. */
    fun screen(screenName: String, properties: Map<String, Any>? = null) {
        val props = properties?.toMutableMap() ?: mutableMapOf()
        props[PROP_PLATFORM] = "android"
        props[PROP_SCREEN_NAME] = screenName
        posthog.screen(screenName, props)
    }

    /** Manually captures a thrown error as a `$exception` event. */
    fun captureException(error: Throwable) {
        posthog.captureException(error)
    }

    // ──────────────────────────────────────────────────────────────────────────
    // High-level semantic event helpers (match iOS event names exactly)
    // ──────────────────────────────────────────────────────────────────────────

    fun trackAppOpened() = capture("app_opened")

    fun trackLogin(method: String) = capture("login", mapOf(PROP_METHOD to method))

    fun trackSignup(method: String) = capture("signup", mapOf(PROP_METHOD to method))

    fun trackAccountCreated() = capture("account_created")

    fun trackLogout() = capture("logout")

    /** User started a scan (channel: image, qr, text, sms, upload). */
    fun trackScanStarted(channel: String) = capture("scan_started", mapOf(PROP_CHANNEL to channel))

    /** Backend analysis started. */
    fun trackAnalysisStarted(channel: String) = capture("analysis_started", mapOf(PROP_CHANNEL to channel))

    /** Scan completed successfully with verdict/score details. */
    fun trackScanCompleted(
        scanId: String,
        verdict: String,
        score: Int,
        channel: String,
        threatCategories: List<String> = emptyList()
    ) = capture("scan_completed", mapOf(
        PROP_SCAN_ID to scanId,
        PROP_VERDICT to verdict,
        PROP_SCORE to score,
        PROP_CHANNEL to channel,
        "threat_categories" to threatCategories
    ))

    /** Backend analysis completed with full details. */
    fun trackAnalysisCompleted(
        scanId: String,
        verdict: String,
        score: Int,
        channel: String,
        threatCategories: List<String> = emptyList(),
        flaggedUrls: List<String> = emptyList()
    ) = capture("analysis_completed", mapOf(
        PROP_SCAN_ID to scanId,
        PROP_VERDICT to verdict,
        PROP_SCORE to score,
        PROP_CHANNEL to channel,
        "threat_categories" to threatCategories,
        "flagged_urls" to flaggedUrls
    ))

    /** Analysis failed — backend error or network failure. */
    fun trackAnalysisFailed(error: String, channel: String) = capture("analysis_failed", mapOf(
        PROP_ERROR to error,
        PROP_CHANNEL to channel
    ))

    /** API request failed (e.g., daily limit reached). */
    fun trackApiRequestFailed(error: String) = capture("api_request_failed", mapOf(PROP_ERROR to error))

    /** User viewed the report/detail screen for a scan. */
    fun trackReportViewed(scanId: String, verdict: String) = capture("report_viewed", mapOf(
        PROP_SCAN_ID to scanId,
        PROP_VERDICT to verdict
    ))

    /** User shared a scan report. */
    fun trackReportShared(scanId: String, method: String) = capture("report_shared", mapOf(
        PROP_SCAN_ID to scanId,
        PROP_METHOD to method
    ))

    /** User changed a setting (e.g., cleared history). */
    fun trackSettingsUpdated(action: String) = capture("settings_updated", mapOf(PROP_ACTION to action))

    /** Camera opened for scan. */
    fun trackCameraOpened() = capture("camera_opened")

    /** Image selected from gallery for scan. */
    fun trackImageSelected() = capture("image_selected")

    // ──────────────────────────────────────────────────────────────────────────
    // Feature Flags
    // ──────────────────────────────────────────────────────────────────────────

    /** Returns true if the given feature flag is enabled for the current user. */
    fun isFeatureEnabled(key: String): Boolean = posthog.isFeatureEnabled(key)

    /** Returns the payload value for a feature flag (String, Number, or JSON). */
    fun featureFlagPayload(key: String): Any? = posthog.getFeatureFlagPayload(key)

    /** Reloads feature flags from the PostHog server. */
    fun reloadFeatureFlags() = posthog.reloadFeatureFlags()

    /** Registers a callback to be invoked when feature flags are reloaded. */
    fun onFeatureFlags(callback: () -> Unit) = posthog.reloadFeatureFlags { callback() }
}