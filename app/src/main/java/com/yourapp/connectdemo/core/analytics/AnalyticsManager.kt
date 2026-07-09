package com.yourapp.connectdemo.core.analytics

import android.app.Application
import com.posthog.PostHog
import com.posthog.PostHogInterface
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AnalyticsManager @Inject constructor(
    private val application: Application
) {
    private val posthog: PostHogInterface by lazy {
        PostHog.Builder(
            application,
            "phc_knJZQWprWxJSt9GNw3ZJUzQ9SgSHLMjTk3Ku4rH8VUVm",
            "https://us.i.posthog.com"
        )
            .captureApplicationLifecycleEvents()
            .captureScreenViews(false)
            .build()
    }

    fun capture(event: String, properties: Map<String, Any>? = null) {
        val props = properties?.toMutableMap() ?: mutableMapOf()
        props.putAll(mapOf("platform" to "android"))
        posthog.capture(event, props)
    }

    fun screen(screenName: String, properties: Map<String, Any>? = null) {
        val props = properties?.toMutableMap() ?: mutableMapOf()
        props.putAll(mapOf("platform" to "android"))
        posthog.screen(screenName, props)
    }

    fun identify(distinctId: String, userProperties: Map<String, Any>? = null) {
        val props = userProperties?.toMutableMap() ?: mutableMapOf()
        props.putAll(mapOf("platform" to "android"))
        posthog.identify(distinctId, props)
    }

    fun reset() {
        posthog.reset()
    }
}
