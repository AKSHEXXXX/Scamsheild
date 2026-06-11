plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    // KSP replaces deprecated KAPT — needed for Hilt 2.51 + AGP 8.4.1
    alias(libs.plugins.ksp)
    // Kotlin Serialization — MUST be declared or @Serializable won't compile
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
}

android {
    namespace  = "com.yourapp.connectdemo"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.yourapp.connectdemo"
        minSdk        = 24
        targetSdk     = 35
        versionCode   = 1
        versionName   = "1.0"

        // ── IMPORTANT ──────────────────────────────────────────────────────────────
        // Replace the placeholder values below with your real Supabase project values.
        // Get them from: Supabase Dashboard → Project Settings → API
        // The app will give a clear error on launch if these are still placeholders
        // (see SupabaseClient.kt — the lazy guard catches this at first access).
        // ─────────────────────────────────────────────────────────────────────────
        buildConfigField("String", "SUPABASE_URL",    "\"https://woudapmpknaqkebfxeck.supabase.co\"")
        buildConfigField("String", "SUPABASE_ANON_KEY", "\"sb_publishable_35kZfTKdcUopu1PPXnw21w_7XA3RWZz\"")

        // Replace with your actual local server IP and port for the Test Connection feature.
        // Format: "http://192.168.X.X:PORT"
        // Note: network_security_config.xml allows cleartext for local IPs (required on API 28+)
        buildConfigField("String", "TARGET_IP", "\"http://192.168.X.X:PORT\"")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables { useSupportLibrary = true }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    buildFeatures {
        compose     = true
        buildConfig = true  // Required to access BuildConfig.SUPABASE_URL etc.
    }

    composeOptions {
        kotlinCompilerExtensionVersion = libs.versions.compose.compiler.get()
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    // ── Compose ──────────────────────────────────────────────────────────────────
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.activity)
    implementation(libs.navigation.compose)
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.lifecycle.runtime.compose)

    // ── Hilt (DI) ────────────────────────────────────────────────────────────────
    // Using KSP processor (not kapt) — faster incremental builds
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)

    // ── Supabase ─────────────────────────────────────────────────────────────────
    implementation(platform(libs.supabase.bom))
    implementation(libs.supabase.postgrest)
    implementation(libs.supabase.auth)
    implementation(libs.supabase.realtime)

    // ── Ktor (HTTP engine for Supabase + local network calls) ────────────────────
    implementation(libs.ktor.android)
    implementation(libs.ktor.logging)
    implementation(libs.ktor.content.negotiation)
    implementation(libs.ktor.serialization.json)

    // ── Serialization runtime ────────────────────────────────────────────────────
    // REQUIRED alongside the kotlin-serialization plugin.
    // Without this, decodeList<MessageModel>() throws ClassNotFoundException at runtime.
    implementation(libs.kotlinx.serialization.json)

    // ── Coil (image loading — future OCR features) ───────────────────────────────
    implementation(libs.coil.compose)

    // ── Debug ─────────────────────────────────────────────────────────────────────
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    // ── Testing ───────────────────────────────────────────────────────────────────
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
}
