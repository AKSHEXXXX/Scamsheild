package com.yourapp.connectdemo.util

object Constants {
    const val TEST_MESSAGE = "Hello from Android"

    // Must match the scheme/host in:
    //   SupabaseClient.kt → install(Auth) { scheme = ...; host = ... }
    //   AndroidManifest.xml → <data android:scheme="..." android:host="..." />
    //   Supabase Dashboard → Authentication → URL Configuration
    const val AUTH_CALLBACK_SCHEME = "com.yourapp.connectdemo"
    const val AUTH_CALLBACK_HOST   = "auth-callback"
    const val AUTH_CALLBACK_URI    = "$AUTH_CALLBACK_SCHEME://$AUTH_CALLBACK_HOST"

    object Routes {
        const val LOGIN = "login"
        const val HOME  = "home"
        // Uncomment when features are implemented:
        // const val OCR     = "ocr"
        // const val SANDBOX = "sandbox"
    }
}
