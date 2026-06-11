package com.yourapp.connectdemo

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/**
 * Application class — required by Hilt for dependency injection.
 * Must be registered in AndroidManifest.xml via android:name=".ConnectDemoApp".
 * Without @HiltAndroidApp, the app crashes on launch with:
 *   "Hilt components were not generated. Check that you have annotated your Application class with @HiltAndroidApp"
 */
@HiltAndroidApp
class ConnectDemoApp : Application()
