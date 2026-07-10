package com.yourapp.connectdemo

import android.app.Application
import com.yourapp.connectdemo.core.analytics.AnalyticsManager
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

/**
 * Application class — required by Hilt for dependency injection.
 * Must be registered in AndroidManifest.xml via android:name=".ConnectDemoApp".
 * Without @HiltAndroidApp, the app crashes on launch with:
 *   "Hilt components were not generated. Check that you have annotated your Application class with @HiltAndroidApp"
 */
@HiltAndroidApp
class ConnectDemoApp : Application() {

    @Inject
    lateinit var analytics: AnalyticsManager

    override fun onCreate() {
        super.onCreate()
        // Initialize analytics to start capturing lifecycle events
        analytics.initialize()
        analytics.trackAppOpened()
    }
}
