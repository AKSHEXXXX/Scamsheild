package com.yourapp.connectdemo.data.remote

import com.yourapp.connectdemo.BuildConfig
import com.yourapp.connectdemo.util.Constants
import io.github.jan.supabase.gotrue.Auth
import io.github.jan.supabase.createSupabaseClient
import io.github.jan.supabase.postgrest.Postgrest
import io.github.jan.supabase.realtime.Realtime

/**
 * Supabase client singleton — provided as `by lazy` for two critical reasons:
 *
 * 1. CRASH PREVENTION: A plain top-level `val` initialises at class-load time, which happens
 *    before onCreate() runs. If SUPABASE_URL still contains the placeholder string, the SDK
 *    throws MalformedURLException and the app crashes before the first screen ever appears.
 *    `by lazy` defers initialisation to first access, and the require() guards give you
 *    a clear, actionable error message instead of a cryptic SDK stack trace.
 *
 * 2. LIFECYCLE SAFETY: Lazy init means the Ktor HttpClient inside the SDK is only created
 *    when actually needed, and the require() checks run after BuildConfig is available.
 *
 * ── BEFORE FIRST BUILD ────────────────────────────────────────────────────────────────────
 * Replace the placeholder values in app/build.gradle.kts:
 *   buildConfigField("String", "SUPABASE_URL",     "\"https://YOUR_PROJECT.supabase.co\"")
 *   buildConfigField("String", "SUPABASE_ANON_KEY", "\"YOUR_ANON_KEY\"")
 * Get real values from: Supabase Dashboard → Project → Settings → API
 * ─────────────────────────────────────────────────────────────────────────────────────────
 */
val supabaseClient by lazy {
    require(!BuildConfig.SUPABASE_URL.contains("YOUR_PROJECT")) {
        "❌ SUPABASE_URL is still a placeholder.\n" +
        "Set the real project URL in app/build.gradle.kts → buildConfigField(\"SUPABASE_URL\", ...).\n" +
        "Get it from: Supabase Dashboard → Project Settings → API → Project URL"
    }
    require(!BuildConfig.SUPABASE_ANON_KEY.contains("YOUR_ANON")) {
        "❌ SUPABASE_ANON_KEY is still a placeholder.\n" +
        "Set the real anon key in app/build.gradle.kts → buildConfigField(\"SUPABASE_ANON_KEY\", ...).\n" +
        "Get it from: Supabase Dashboard → Project Settings → API → anon public key"
    }

    createSupabaseClient(
        supabaseUrl = BuildConfig.SUPABASE_URL,
        supabaseKey = BuildConfig.SUPABASE_ANON_KEY
    ) {
        install(Auth) {
            // These must match the intent-filter in AndroidManifest.xml exactly.
            // Also add "com.yourapp.connectdemo://auth-callback" in:
            // Supabase Dashboard → Authentication → URL Configuration → Redirect URLs
            scheme = Constants.AUTH_CALLBACK_SCHEME
            host   = Constants.AUTH_CALLBACK_HOST
        }
        install(Postgrest)
        install(Realtime)  // Scaffolded for real-time message updates in future iterations
    }
}
