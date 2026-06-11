# Android App Build Spec — Supabase + OAuth + Test Connection
> **Coding Agent Instructions**: Follow each phase in order. Do not skip phases. Run all validation checks before advancing.

---

## Overview

Build a production-ready Android app using **Jetpack Compose** with the following core features:

1. **Test Connection Screen** — A button that sends `"Hello from Android"` to a local network IP address (configurable)
2. **OAuth Login Screen** — Google OAuth via Supabase Auth
3. **Supabase DB Integration** — POST and GET operations on a Supabase table
4. **Future-ready Architecture** — Scaffolded for OCR, sandboxing, and feature expansion

**Tech Stack:**
- Language: Kotlin
- UI: Jetpack Compose
- Auth + DB: Supabase (official Android SDK)
- HTTP Client: Ktor (Supabase uses it internally; also used for local IP calls)
- DI: Hilt
- Architecture: MVVM + Repository pattern
- Navigation: Jetpack Compose Navigation
- Async: Kotlin Coroutines + Flow

---

## Phase 0 — Project Bootstrapping

### 0.1 Create Project
- Open Android Studio → New Project → **Empty Activity (Compose)**
- Package name: `com.yourapp.connectdemo`
- Min SDK: **24** (Android 7.0)
- Target SDK: **35**
- Language: **Kotlin**
- Build system: **Gradle (Kotlin DSL)**

### 0.2 Directory Structure
Create the following package structure under `app/src/main/java/com/yourapp/connectdemo/`:

```
com/yourapp/connectdemo/
├── MainActivity.kt
├── di/
│   └── AppModule.kt
├── data/
│   ├── remote/
│   │   ├── SupabaseClient.kt
│   │   └── LocalNetworkClient.kt
│   ├── repository/
│   │   ├── AuthRepository.kt
│   │   └── DataRepository.kt
│   └── model/
│       └── MessageModel.kt
├── ui/
│   ├── theme/
│   │   ├── Color.kt
│   │   ├── Theme.kt
│   │   └── Type.kt
│   ├── navigation/
│   │   └── AppNavGraph.kt
│   ├── auth/
│   │   ├── LoginScreen.kt
│   │   └── LoginViewModel.kt
│   └── home/
│       ├── HomeScreen.kt
│       └── HomeViewModel.kt
└── util/
    ├── Constants.kt
    └── Result.kt
```

### ✅ Phase 0 Validation
- [ ] Project compiles and launches on emulator/device with default "Hello Android" screen
- [ ] No Gradle sync errors

---

## Phase 1 — Dependency Configuration

### 1.1 `libs.versions.toml` (Version Catalog)
Add to `gradle/libs.versions.toml`:

```toml
[versions]
kotlin = "1.9.23"
compose-bom = "2024.05.00"
compose-compiler = "1.5.13"
hilt = "2.51"
supabase = "2.4.0"
ktor = "2.3.11"
navigation-compose = "2.7.7"
lifecycle = "2.8.0"
coil = "2.6.0"
ksp = "1.9.23-1.0.20"  # Must match kotlin version exactly

[libraries]
# Compose
compose-bom = { group = "androidx.compose", name = "compose-bom", version.ref = "compose-bom" }
compose-ui = { group = "androidx.compose.ui", name = "ui" }
compose-ui-tooling = { group = "androidx.compose.ui", name = "ui-tooling-preview" }
compose-material3 = { group = "androidx.compose.material3", name = "material3" }
compose-activity = { group = "androidx.activity", name = "activity-compose", version = "1.9.0" }

# Navigation
navigation-compose = { group = "androidx.navigation", name = "navigation-compose", version.ref = "navigation-compose" }

# Lifecycle + ViewModel
lifecycle-viewmodel-compose = { group = "androidx.lifecycle", name = "lifecycle-viewmodel-compose", version.ref = "lifecycle" }
lifecycle-runtime-compose = { group = "androidx.lifecycle", name = "lifecycle-runtime-compose", version.ref = "lifecycle" }

# Hilt
hilt-android = { group = "com.google.dagger", name = "hilt-android", version.ref = "hilt" }
hilt-compiler = { group = "com.google.dagger", name = "hilt-android-compiler", version.ref = "hilt" }
hilt-navigation-compose = { group = "androidx.hilt", name = "hilt-navigation-compose", version = "1.2.0" }

# Supabase
supabase-bom = { group = "io.github.jan-tennert.supabase", name = "bom", version.ref = "supabase" }
supabase-postgrest = { group = "io.github.jan-tennert.supabase", name = "postgrest-kt" }
supabase-auth = { group = "io.github.jan-tennert.supabase", name = "auth-kt" }
supabase-realtime = { group = "io.github.jan-tennert.supabase", name = "realtime-kt" }

# Ktor (Supabase engine)
ktor-android = { group = "io.ktor", name = "ktor-client-android", version.ref = "ktor" }
ktor-logging = { group = "io.ktor", name = "ktor-client-logging", version.ref = "ktor" }

# Coil (image loading — for future OCR/image features)
coil-compose = { group = "io.coil-kt", name = "coil-compose", version.ref = "coil" }

# Serialization (REQUIRED — MessageModel uses @Serializable; without this the project won't compile)
kotlinx-serialization-json = { group = "org.jetbrains.kotlinx", name = "kotlinx-serialization-json", version = "1.6.3" }

[plugins]
android-application = { id = "com.android.application", version = "8.4.1" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
# KSP replaces deprecated KAPT — required for Hilt 2.51 + AGP 8.4
ksp = { id = "com.google.devtools.ksp", version.ref = "ksp" }
# Serialization plugin — required for @Serializable on MessageModel
kotlin-serialization = { id = "org.jetbrains.kotlin.plugin.serialization", version.ref = "kotlin" }
hilt = { id = "com.google.dagger.hilt.android", version.ref = "hilt" }
```

### 1.2 `app/build.gradle.kts`

```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    // KSP replaces KAPT — required for Hilt 2.51 + AGP 8.4.1 compatibility
    alias(libs.plugins.ksp)
    // Kotlin Serialization plugin — MUST be here or @Serializable won't compile
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
}

android {
    namespace = "com.yourapp.connectdemo"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.yourapp.connectdemo"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        // Supabase config — replace with real values
        buildConfigField("String", "SUPABASE_URL", "\"https://YOUR_PROJECT.supabase.co\"")
        buildConfigField("String", "SUPABASE_ANON_KEY", "\"YOUR_ANON_KEY\"")
        buildConfigField("String", "TARGET_IP", "\"http://192.168.X.X:PORT\"")
    }

    buildFeatures {
        compose = true
        buildConfig = true
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
}

dependencies {
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling)
    implementation(libs.compose.material3)
    implementation(libs.compose.activity)
    implementation(libs.navigation.compose)
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.lifecycle.runtime.compose)

    // Hilt — using KSP (not KAPT) for faster builds and AGP 8.4 compatibility
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)

    // Supabase
    implementation(platform(libs.supabase.bom))
    implementation(libs.supabase.postgrest)
    implementation(libs.supabase.auth)
    implementation(libs.supabase.realtime)

    // Ktor engine
    implementation(libs.ktor.android)
    implementation(libs.ktor.logging)

    // Coil
    implementation(libs.coil.compose)

    // Serialization runtime — REQUIRED alongside the plugin; decodeList<MessageModel>() needs this
    implementation(libs.kotlinx.serialization.json)

    // Debug
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    // Testing
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
}
```

### 1.3 `AndroidManifest.xml` Permissions
Add to `<manifest>` block before `<application>`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
```

Add inside `<application>` for OAuth deep-link handling:

```xml
<activity
    android:name=".MainActivity"
    android:exported="true"
    android:launchMode="singleTask">
    <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
    </intent-filter>
    <!-- OAuth callback deep link -->
    <intent-filter>
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data
            android:scheme="com.yourapp.connectdemo"
            android:host="auth-callback" />
    </intent-filter>
</activity>
```

### ✅ Phase 1 Validation
- [ ] Gradle sync succeeds with no errors
- [ ] `Build → Clean Project` then `Build → Make Project` — zero errors
- [ ] All library imports resolve in the IDE

### 1.4 `res/xml/network_security_config.xml` ⚠️ MANDATORY

> **Why this is Phase 1, not optional**: Android 9+ (API 28+) blocks **all** cleartext HTTP traffic by default. Since `TARGET_IP` uses `http://` and `minSdk = 24` (so devices running API 28+ will be targeted), tapping "Test Connection" crashes with `IOException: Cleartext HTTP traffic not permitted` without this file. Create it **before first build**, not as a Phase 10 fix.

Create `app/src/main/res/xml/network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <!-- Allow cleartext traffic ONLY to local network IPs for the Test Connection feature -->
    <!-- Replace 192.168.X.X with your actual subnet, e.g. 192.168.1.0 -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">192.168.1.0</domain>
        <!-- Add more local subnet entries here as needed -->
    </domain-config>
    <!-- All other traffic (Supabase) goes over HTTPS — no changes needed -->
</network-security-config>
```

Then reference it in `AndroidManifest.xml` inside the `<application>` tag:

```xml
<application
    android:name=".ConnectDemoApp"
    android:networkSecurityConfig="@xml/network_security_config"
    ... >
```

---

## Phase 2 — Core Utilities & Constants

### 2.1 `util/Constants.kt`

```kotlin
package com.yourapp.connectdemo.util

object Constants {
    // Populated from BuildConfig at runtime
    const val TEST_MESSAGE = "Hello from Android"
    const val AUTH_CALLBACK_SCHEME = "com.yourapp.connectdemo://auth-callback"

    // Navigation routes
    object Routes {
        const val LOGIN = "login"
        const val HOME = "home"
        // Future: const val OCR = "ocr"
        // Future: const val SANDBOX = "sandbox"
    }
}
```

### 2.2 `util/Result.kt`

```kotlin
package com.yourapp.connectdemo.util

sealed class Result<out T> {
    data class Success<T>(val data: T) : Result<T>()
    data class Error(val message: String, val cause: Throwable? = null) : Result<Nothing>()
    object Loading : Result<Nothing>()
}
```

### 2.3 `data/model/MessageModel.kt`

```kotlin
package com.yourapp.connectdemo.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class MessageModel(
    val id: Long? = null,
    val content: String,
    @SerialName("created_at")
    val createdAt: String? = null,
    @SerialName("user_id")
    val userId: String? = null
)
```

---

## Phase 3 — Supabase Client Setup

### 3.1 Supabase Project Setup (Do this before coding)
1. Go to [supabase.com](https://supabase.com) → New Project
2. Copy **Project URL** and **anon public key** into `buildConfigField` in `build.gradle.kts`
3. In Supabase SQL Editor, run:

```sql
-- Create messages table
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to insert
CREATE POLICY "Users can insert own messages"
ON messages FOR INSERT TO authenticated
WITH CHECK (auth.uid() = user_id);

-- Allow authenticated users to read all messages
CREATE POLICY "Users can read messages"
ON messages FOR SELECT TO authenticated
USING (true);
```

4. In Supabase Dashboard → Authentication → Providers → Enable **Google**
5. Add OAuth credentials (Google Cloud Console → OAuth 2.0 Client)
6. Add redirect URL: `com.yourapp.connectdemo://auth-callback`

### 3.2 `data/remote/SupabaseClient.kt`

```kotlin
package com.yourapp.connectdemo.data.remote

import com.yourapp.connectdemo.BuildConfig
import io.github.jan.supabase.auth.Auth
import io.github.jan.supabase.createSupabaseClient
import io.github.jan.supabase.postgrest.Postgrest
import io.github.jan.supabase.realtime.Realtime

// ⚠️  LAZY is critical here.
// A plain `val` initialises at class-load time — before onCreate runs.
// If SUPABASE_URL still contains the placeholder string "YOUR_PROJECT", the SDK
// throws MalformedURLException and the app crashes before the first screen appears.
// `by lazy` defers initialisation to first access, and the require() guard gives a
// clear, actionable error message instead of a cryptic SDK stack trace.
val supabaseClient by lazy {
    require(!BuildConfig.SUPABASE_URL.contains("YOUR_PROJECT")) {
        "SUPABASE_URL is still a placeholder. Set the real value in build.gradle.kts " +
        "or preferably via local.properties + secrets-gradle-plugin."
    }
    require(!BuildConfig.SUPABASE_ANON_KEY.contains("YOUR_ANON")) {
        "SUPABASE_ANON_KEY is still a placeholder. Set the real anon key."
    }
    createSupabaseClient(
        supabaseUrl = BuildConfig.SUPABASE_URL,
        supabaseKey = BuildConfig.SUPABASE_ANON_KEY
    ) {
        install(Auth) {
            scheme = "com.yourapp.connectdemo"
            host = "auth-callback"
        }
        install(Postgrest)
        install(Realtime) // Ready for real-time features
    }
}
```


### 3.3 `data/remote/LocalNetworkClient.kt`
> This powers the "Test Connection" button from the screenshot.

```kotlin
package com.yourapp.connectdemo.data.remote

import io.ktor.client.*
import io.ktor.client.engine.android.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.plugins.logging.*
import io.ktor.client.request.*
import io.ktor.client.statement.*
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*

class LocalNetworkClient {

    private val client = HttpClient(Android) {
        install(ContentNegotiation) {
            json()
        }
        install(Logging) {
            logger = Logger.DEFAULT
            level = LogLevel.ALL
        }
        engine {
            connectTimeout = 10_000
            socketTimeout = 10_000
        }
    }

    /**
     * Sends "Hello from Android" as plain text POST to the target local IP.
     * targetUrl format: "http://192.168.X.X:PORT/endpoint"
     */
    suspend fun sendHelloMessage(targetUrl: String, message: String): Result<String> {
        return try {
            val response: HttpResponse = client.post(targetUrl) {
                contentType(ContentType.Text.Plain)
                setBody(message)
            }
            if (response.status.isSuccess()) {
                Result.Success(response.bodyAsText())
            } else {
                Result.Error("Server returned ${response.status.value}")
            }
        } catch (e: Exception) {
            Result.Error("Connection failed: ${e.message}", e)
        }
    }

    fun close() = client.close()
}
```

---

## Phase 4 — Repository Layer

### 4.1 `data/repository/AuthRepository.kt`

```kotlin
package com.yourapp.connectdemo.data.repository

import com.yourapp.connectdemo.data.remote.supabaseClient
import com.yourapp.connectdemo.util.Result
import io.github.jan.supabase.auth.auth
import io.github.jan.supabase.auth.providers.Google
import io.github.jan.supabase.auth.user.UserInfo
import io.github.jan.supabase.auth.SessionStatus
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor() {

    val currentUser: UserInfo?
        get() = supabaseClient.auth.currentUserOrNull()

    val isLoggedIn: Boolean
        get() = currentUser != null

    /**
     * Observe the Supabase auth session status as a stream.
     * The ViewModel should use this to drive navigation — NOT the return value
     * of signInWithGoogle(), which only tells you "the browser was launched".
     * Authenticated = user completed OAuth and session was imported via deep-link.
     */
    val isAuthenticated: Flow<Boolean> =
        supabaseClient.auth.sessionStatus.map { status ->
            status is SessionStatus.Authenticated
        }

    /**
     * Launches the Google OAuth flow by opening a Chrome Custom Tab.
     * ⚠️  This does NOT block until auth is complete.
     * Success comes back via onNewIntent → handleAuthCallback().
     * Observe [isAuthenticated] Flow to react to the actual login result.
     */
    fun signInWithGoogle(): Flow<Result<Unit>> = flow {
        emit(Result.Loading)
        try {
            supabaseClient.auth.signInWith(Google) {
                // scheme/host set in SupabaseClient.kt — matches Manifest deep-link
            }
            // ✅ Emit Loading (not Success) — auth isn't done yet.
            // The browser is now open. Real completion comes via handleAuthCallback().
            // Do NOT emit Result.Success here — that was the original bug.
            emit(Result.Loading)
        } catch (e: Exception) {
            emit(Result.Error("Google Sign-In failed: ${e.message}", e))
        }
    }

    fun signOut(): Flow<Result<Unit>> = flow {
        emit(Result.Loading)
        try {
            supabaseClient.auth.signOut()
            emit(Result.Success(Unit))
        } catch (e: Exception) {
            emit(Result.Error("Sign out failed: ${e.message}", e))
        }
    }

    /**
     * Call this from MainActivity.onNewIntent to handle the OAuth callback deep link.
     * This is where the session is actually established after the browser redirects back.
     */
    suspend fun handleAuthCallback(url: String) {
        supabaseClient.auth.parseFragmentAndImportSession(url)
    }
}
```


### 4.2 `data/repository/DataRepository.kt`

```kotlin
package com.yourapp.connectdemo.data.repository

import com.yourapp.connectdemo.BuildConfig
import com.yourapp.connectdemo.data.model.MessageModel
import com.yourapp.connectdemo.data.remote.LocalNetworkClient
import com.yourapp.connectdemo.data.remote.supabaseClient
import com.yourapp.connectdemo.util.Constants
import com.yourapp.connectdemo.util.Result
import io.github.jan.supabase.auth.auth
import io.github.jan.supabase.postgrest.postgrest
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DataRepository @Inject constructor(
    private val localNetworkClient: LocalNetworkClient
) {

    // ── Local Network (Test Connection) ──────────────────────────

    fun sendTestMessage(): Flow<Result<String>> = flow {
        emit(Result.Loading)
        val result = localNetworkClient.sendHelloMessage(
            targetUrl = BuildConfig.TARGET_IP,
            message = Constants.TEST_MESSAGE
        )
        emit(result)
    }

    // ── Supabase: POST ────────────────────────────────────────────

    fun postMessage(content: String): Flow<Result<Unit>> = flow {
        emit(Result.Loading)
        try {
            val userId = supabaseClient.auth.currentUserOrNull()?.id
                ?: throw Exception("User not authenticated")

            supabaseClient.postgrest["messages"].insert(
                MessageModel(content = content, userId = userId)
            )
            emit(Result.Success(Unit))
        } catch (e: Exception) {
            emit(Result.Error("Post failed: ${e.message}", e))
        }
    }

    // ── Supabase: GET ─────────────────────────────────────────────

    fun getMessages(): Flow<Result<List<MessageModel>>> = flow {
        emit(Result.Loading)
        try {
            val messages = supabaseClient.postgrest["messages"]
                .select()
                .decodeList<MessageModel>()
            emit(Result.Success(messages))
        } catch (e: Exception) {
            emit(Result.Error("Fetch failed: ${e.message}", e))
        }
    }
}
```

---

## Phase 5 — Dependency Injection (Hilt)

### 5.1 `ConnectDemoApp.kt` (Application class)

```kotlin
package com.yourapp.connectdemo

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class ConnectDemoApp : Application()
```

> **Add to AndroidManifest.xml** inside `<application>`:
> `android:name=".ConnectDemoApp"`

### 5.2 `di/AppModule.kt`

```kotlin
package com.yourapp.connectdemo.di

import com.yourapp.connectdemo.data.remote.LocalNetworkClient
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideLocalNetworkClient(): LocalNetworkClient = LocalNetworkClient()
}
```

---

## Phase 6 — Navigation

### 6.1 `ui/navigation/AppNavGraph.kt`

```kotlin
package com.yourapp.connectdemo.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.yourapp.connectdemo.ui.auth.LoginScreen
import com.yourapp.connectdemo.ui.home.HomeScreen
import com.yourapp.connectdemo.util.Constants.Routes

@Composable
fun AppNavGraph(
    navController: NavHostController,
    startDestination: String
) {
    NavHost(navController = navController, startDestination = startDestination) {

        composable(Routes.LOGIN) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Routes.HOME) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.HOME) {
            HomeScreen(
                onLogout = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(Routes.HOME) { inclusive = true }
                    }
                }
            )
        }

        // Future routes — scaffold only
        // composable(Routes.OCR) { OcrScreen() }
        // composable(Routes.SANDBOX) { SandboxScreen() }
    }
}
```

---

## Phase 7 — Login Screen (OAuth)

### 7.1 `ui/auth/LoginViewModel.kt`

```kotlin
package com.yourapp.connectdemo.ui.auth

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.yourapp.connectdemo.data.repository.AuthRepository
import com.yourapp.connectdemo.util.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import javax.inject.Inject

data class LoginUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val isSuccess: Boolean = false
)

// AndroidViewModel — gives us Application context without passing Context into repos or composables.
@HiltViewModel
class LoginViewModel @Inject constructor(
    application: Application,
    private val authRepository: AuthRepository
) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    init {
        // ✅ Observe the REAL auth state from Supabase.
        // isAuthenticated emits true only after the OAuth deep-link callback
        // has imported the session — this is the correct signal to navigate to Home.
        authRepository.isAuthenticated
            .onEach { authenticated ->
                if (authenticated) {
                    _uiState.value = LoginUiState(isSuccess = true)
                }
            }
            .launchIn(viewModelScope)
    }

    fun signInWithGoogle() {
        // No context needed — AndroidViewModel provides Application via getApplication()
        authRepository.signInWithGoogle()
            .onEach { result ->
                when (result) {
                    // Loading = "browser is opening" — correct, auth not done yet
                    is Result.Loading -> _uiState.value = LoginUiState(isLoading = true)
                    // Success is never emitted from signInWithGoogle (fixed in AuthRepository).
                    // Real success comes via the isAuthenticated Flow observer in init{}.
                    is Result.Success -> { /* handled by isAuthenticated observer */ }
                    is Result.Error -> _uiState.value = LoginUiState(error = result.message)
                }
            }
            .launchIn(viewModelScope)
    }
}
```


### 7.2 `ui/auth/LoginScreen.kt`

```kotlin
package com.yourapp.connectdemo.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit,
    viewModel: LoginViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    // No LocalContext needed — ViewModel uses AndroidViewModel for application context

    // Navigate on success
    LaunchedEffect(uiState.isSuccess) {
        if (uiState.isSuccess) onLoginSuccess()
    }

    Scaffold { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(24.dp),
                modifier = Modifier.padding(32.dp)
            ) {
                Text(
                    text = "Connect Demo",
                    fontSize = 28.sp,
                    fontWeight = FontWeight.Bold
                )

                Text(
                    text = "Sign in to continue",
                    fontSize = 16.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                Spacer(modifier = Modifier.height(16.dp))

                Button(
                    onClick = { viewModel.signInWithGoogle() },
                    enabled = !uiState.isLoading,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp)
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text("Sign in with Google", fontSize = 16.sp)
                    }
                }

                uiState.error?.let { error ->
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer
                        )
                    ) {
                        Text(
                            text = error,
                            modifier = Modifier.padding(12.dp),
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            fontSize = 13.sp
                        )
                    }
                }
            }
        }
    }
}
```

---

## Phase 8 — Home Screen (Test Connection + Supabase DB)

### 8.1 `ui/home/HomeViewModel.kt`

```kotlin
package com.yourapp.connectdemo.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourapp.connectdemo.data.model.MessageModel
import com.yourapp.connectdemo.data.repository.AuthRepository
import com.yourapp.connectdemo.data.repository.DataRepository
import com.yourapp.connectdemo.util.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import javax.inject.Inject

data class HomeUiState(
    val isLoading: Boolean = false,
    val connectionStatus: String? = null,
    val messages: List<MessageModel> = emptyList(),
    val error: String? = null,
    val postSuccess: Boolean = false,
    // ✅ Added: drives signOut navigation from state, not from a fire-and-forget call
    val isLoggedOut: Boolean = false
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val dataRepository: DataRepository,
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    val currentUser get() = authRepository.currentUser

    // ── Test Connection (from screenshot requirement) ────────────

    fun sendTestMessage() {
        dataRepository.sendTestMessage()
            .onEach { result ->
                when (result) {
                    is Result.Loading -> _uiState.value = _uiState.value.copy(
                        isLoading = true, connectionStatus = null, error = null
                    )
                    is Result.Success -> _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        connectionStatus = "✅ Sent! Response: ${result.data}"
                    )
                    is Result.Error -> _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = result.message
                    )
                }
            }
            .launchIn(viewModelScope)
    }

    // ── Supabase GET ─────────────────────────────────────────────

    fun fetchMessages() {
        dataRepository.getMessages()
            .onEach { result ->
                when (result) {
                    is Result.Loading -> _uiState.value = _uiState.value.copy(isLoading = true)
                    is Result.Success -> _uiState.value = _uiState.value.copy(
                        isLoading = false, messages = result.data
                    )
                    is Result.Error -> _uiState.value = _uiState.value.copy(
                        isLoading = false, error = result.message
                    )
                }
            }
            .launchIn(viewModelScope)
    }

    // ── Supabase POST ─────────────────────────────────────────────

    fun postToDatabase(content: String) {
        dataRepository.postMessage(content)
            .onEach { result ->
                when (result) {
                    is Result.Loading -> _uiState.value = _uiState.value.copy(isLoading = true)
                    is Result.Success -> {
                        // ✅ Set postSuccess first and finish this coroutine frame.
                        // LaunchedEffect in HomeScreen will observe postSuccess=true and clear postText.
                        // fetchMessages() is launched separately so it doesn't immediately
                        // overwrite postSuccess=true with isLoading=true before the UI reacts.
                        _uiState.value = _uiState.value.copy(
                            isLoading = false, postSuccess = true
                        )
                        viewModelScope.launch {
                            fetchMessages() // Refresh list — in a separate launch to avoid race
                        }
                    }
                    is Result.Error -> _uiState.value = _uiState.value.copy(
                        isLoading = false, error = result.message
                    )
                }
            }
            .launchIn(viewModelScope)
    }

    // ✅ signOut now observes the result — navigation is driven from isLoggedOut state.
    // Previously: signOut() was fire-and-forget and onLogout() was called immediately
    // in the UI, racing with the async sign-out operation.
    fun signOut() {
        authRepository.signOut()
            .onEach { result ->
                when (result) {
                    is Result.Loading -> _uiState.value = _uiState.value.copy(isLoading = true)
                    is Result.Success -> _uiState.value = _uiState.value.copy(
                        isLoading = false, isLoggedOut = true
                    )
                    is Result.Error -> _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Sign out failed: ${result.message}"
                    )
                }
            }
            .launchIn(viewModelScope)
    }

    fun clearError() { _uiState.value = _uiState.value.copy(error = null) }
}
```

### 8.2 `ui/home/HomeScreen.kt`

```kotlin
package com.yourapp.connectdemo.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onLogout: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    var postText by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        viewModel.fetchMessages()
    }

    LaunchedEffect(uiState.postSuccess) {
        if (uiState.postSuccess) postText = ""
    }

    // ✅ Navigation driven from state — fires only after sign-out actually succeeds.
    // Previously: onLogout() was called synchronously with signOut() in the onClick,
    // racing the async Supabase sign-out and leaving an active session on the Login screen.
    LaunchedEffect(uiState.isLoggedOut) {
        if (uiState.isLoggedOut) onLogout()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Connect Demo") },
                actions = {
                    IconButton(onClick = {
                        // ✅ Just trigger the sign-out — do NOT call onLogout() here.
                        // Navigation happens via LaunchedEffect(uiState.isLoggedOut) above,
                        // which waits for the sign-out Flow to emit Success.
                        viewModel.signOut()
                    }) {
                        Icon(Icons.Default.ExitToApp, contentDescription = "Sign Out")
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item { Spacer(Modifier.height(8.dp)) }

            // ── User info ──
            uiState.let {
                item {
                    Text(
                        text = "Logged in as: ${viewModel.currentUser?.email ?: "Unknown"}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            // ── TEST CONNECTION BUTTON (core requirement from screenshot) ──
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text("Local Network Test", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "Sends \"Hello from Android\" to the configured IP.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Button(
                            onClick = { viewModel.sendTestMessage() },
                            enabled = !uiState.isLoading,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Test Connection")
                        }
                        uiState.connectionStatus?.let {
                            Text(it, fontSize = 13.sp, color = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }

            // ── POST TO SUPABASE ──
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text("Post to Supabase", style = MaterialTheme.typography.titleMedium)
                        OutlinedTextField(
                            value = postText,
                            onValueChange = { postText = it },
                            label = { Text("Message") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true
                        )
                        Button(
                            onClick = { if (postText.isNotBlank()) viewModel.postToDatabase(postText) },
                            enabled = postText.isNotBlank() && !uiState.isLoading,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("POST to DB")
                        }
                    }
                }
            }

            // ── GET FROM SUPABASE ──
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Messages from DB", style = MaterialTheme.typography.titleMedium)
                    TextButton(onClick = { viewModel.fetchMessages() }) {
                        Text("Refresh")
                    }
                }
            }

            if (uiState.isLoading) {
                item {
                    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(modifier = Modifier.size(32.dp))
                    }
                }
            }

            if (uiState.messages.isEmpty() && !uiState.isLoading) {
                item {
                    Text(
                        "No messages yet. Post something above.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            items(uiState.messages) { msg ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant
                    )
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(msg.content, style = MaterialTheme.typography.bodyMedium)
                        msg.createdAt?.let {
                            Text(
                                it,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }

            // ── Error Banner ──
            uiState.error?.let { error ->
                item {
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer
                        ),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                error,
                                color = MaterialTheme.colorScheme.onErrorContainer,
                                modifier = Modifier.weight(1f),
                                fontSize = 13.sp
                            )
                            TextButton(onClick = { viewModel.clearError() }) {
                                Text("Dismiss")
                            }
                        }
                    }
                }
            }

            item { Spacer(Modifier.height(32.dp)) }
        }
    }
}
```

---

## Phase 9 — MainActivity (Entry Point + OAuth Callback)

### 9.1 `MainActivity.kt`

```kotlin
package com.yourapp.connectdemo

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.lifecycleScope
import androidx.navigation.compose.rememberNavController
import com.yourapp.connectdemo.data.remote.supabaseClient
import com.yourapp.connectdemo.ui.navigation.AppNavGraph
import com.yourapp.connectdemo.ui.theme.ConnectDemoTheme
import com.yourapp.connectdemo.util.Constants.Routes
import dagger.hilt.android.AndroidEntryPoint
import io.github.jan.supabase.auth.auth
import kotlinx.coroutines.launch
// ✅ runBlocking is intentionally REMOVED — it caused ANR when parseFragmentAndImportSession
// made a network call on the main thread. Use lifecycleScope.launch instead.

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Determine start destination based on auth state
        val startDestination = if (supabaseClient.auth.currentUserOrNull() != null) {
            Routes.HOME
        } else {
            Routes.LOGIN
        }

        setContent {
            ConnectDemoTheme {
                val navController = rememberNavController()
                AppNavGraph(
                    navController = navController,
                    startDestination = startDestination
                )
            }
        }
    }

    // Handle OAuth deep-link callback
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        // ✅ setIntent is required with launchMode="singleTask" so subsequent
        // getIntent() calls return the new intent with the auth callback URI.
        setIntent(intent)
        val uri = intent.data?.toString() ?: return
        if (uri.startsWith("com.yourapp.connectdemo://auth-callback")) {
            // ✅ lifecycleScope.launch — NOT runBlocking.
            // parseFragmentAndImportSession makes a network call to exchange the OAuth token.
            // runBlocking on the main thread blocks the UI thread and causes ANR on slow networks.
            // lifecycleScope is automatically cancelled when the Activity is destroyed.
            lifecycleScope.launch {
                supabaseClient.auth.parseFragmentAndImportSession(uri)
                // After this completes, the auth.sessionStatus Flow emits Authenticated,
                // which LoginViewModel observes and sets isSuccess = true → navigates to Home.
            }
        }
    }
}
```


---

## Phase 10 — Testing & Debugging Checklist

### 10.1 Build Verification Tests

Run these before proceeding to device testing:

```bash
# Clean build
./gradlew clean assembleDebug

# Run unit tests
./gradlew testDebugUnitTest

# Check for lint errors
./gradlew lintDebug
```

Expected: Zero errors, zero critical lint warnings.

### 10.2 Emulator Tests

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| **Cold launch — not logged in** | Fresh install, launch | Login screen shown |
| **Cold launch — logged in** | Install after prior login, launch | Home screen shown directly |
| **Google OAuth flow** | Tap "Sign in with Google" | Browser/Chrome Custom Tab opens → returns to app → Home screen |
| **Auth callback deep link** | Complete OAuth in browser | App resumes at Home screen, not Login |
| **Test Connection — valid IP** | Set `TARGET_IP`, tap "Test Connection" | Status shows `✅ Sent!` |
| **Test Connection — invalid IP** | Set garbage IP, tap button | Error card: "Connection failed" |
| **POST to Supabase** | Type message, tap POST | Message appears in DB list after refresh |
| **GET from Supabase** | Tap Refresh | All messages from DB appear in list |
| **Sign Out** | Tap logout icon | Returns to Login screen; session cleared |

### 10.3 Common Bugs & Fixes

**Bug: `CLEARTEXT communication not permitted`**
- Fix: If `TARGET_IP` is `http://` (not `https://`), add to `res/xml/network_security_config.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">192.168.X.X</domain>
    </domain-config>
</network-security-config>
```
And reference it in `AndroidManifest.xml`:
```xml
android:networkSecurityConfig="@xml/network_security_config"
```

**Bug: OAuth browser does not return to app**
- Fix: Verify `android:launchMode="singleTask"` in Manifest. Verify `scheme` and `host` in `SupabaseClient.kt` match the Supabase dashboard redirect URL exactly.

**Bug: `PGRST301 - RLS policy violation` on POST**
- Fix: Verify user is authenticated, `user_id` is set correctly in `postMessage()`, and the RLS INSERT policy includes `WITH CHECK (auth.uid() = user_id)`.

**Bug: Hilt injection crashes on launch**
- Fix: Ensure `@HiltAndroidApp` is on `ConnectDemoApp`, and `android:name=".ConnectDemoApp"` is set in Manifest.

**Bug: `@Serializable` not found**
- Fix: Add to `build.gradle.kts`:
```kotlin
plugins {
    id("org.jetbrains.kotlin.plugin.serialization") version "1.9.23"
}
dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
}
```

---

## Phase 11 — Future Feature Scaffolding

These stubs are **non-functional placeholders** — they establish the file and route structure so future features can be slotted in without refactoring.

### 11.1 OCR Feature Stub
Create `ui/ocr/OcrScreen.kt`:

```kotlin
package com.yourapp.connectdemo.ui.ocr

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

// FUTURE FEATURE: OCR integration
// Planned: Camera capture → ML Kit Text Recognition → POST result to Supabase
// Dependencies to add when ready:
//   implementation("com.google.mlkit:text-recognition:16.0.0")
//   implementation("androidx.camera:camera-camera2:1.3.0")

@Composable
fun OcrScreen() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text("OCR — Coming Soon", style = MaterialTheme.typography.headlineMedium)
    }
}
```

### 11.2 Sandbox Feature Stub
Create `ui/sandbox/SandboxScreen.kt`:

```kotlin
package com.yourapp.connectdemo.ui.sandbox

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

// FUTURE FEATURE: Sandboxed execution environment
// Planned: Isolated WebView or script runner for untrusted content evaluation

@Composable
fun SandboxScreen() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text("Sandbox — Coming Soon", style = MaterialTheme.typography.headlineMedium)
    }
}
```

### 11.3 Extend `Constants.kt` for Future Routes

```kotlin
// Uncomment these when features are implemented:
// const val OCR = "ocr"
// const val SANDBOX = "sandbox"
```

---

## Phase 12 — Final Checklist Before Handoff

### 12.1 Security
- [ ] `SUPABASE_URL` and `SUPABASE_ANON_KEY` are in `buildConfigField`, not hardcoded in source
- [ ] `TARGET_IP` is in `buildConfigField`
- [ ] `.gitignore` includes `local.properties`
- [ ] RLS is enabled on all Supabase tables
- [ ] No secrets committed to git

### 12.2 Architecture
- [ ] All ViewModel state exposed as `StateFlow` (not `LiveData`)
- [ ] No business logic in Composables — all in ViewModel/Repository
- [ ] Repository layer is the single source of truth
- [ ] Hilt provides all dependencies — no manual instantiation
- [ ] `Result<T>` sealed class used throughout for error handling

### 12.3 UX
- [ ] Loading states shown for all async operations
- [ ] Error states surfaced with dismiss option
- [ ] Back navigation works correctly throughout
- [ ] App recovers gracefully from network failure (no crash)

### 12.4 Extensibility Confirmation
- [ ] `AppNavGraph` has commented route stubs for OCR and Sandbox
- [ ] `OcrScreen.kt` and `SandboxScreen.kt` placeholder files exist
- [ ] `DataRepository` is structured so new data sources slot in as additional methods
- [ ] `MessageModel` uses `@Serializable` for forward compatibility

---

## Summary of Files to Create

| File | Phase |
|------|-------|
| `gradle/libs.versions.toml` | 1 |
| `app/build.gradle.kts` | 1 |
| `AndroidManifest.xml` (edited) | 1 + 5 |
| `util/Constants.kt` | 2 |
| `util/Result.kt` | 2 |
| `data/model/MessageModel.kt` | 2 |
| `data/remote/SupabaseClient.kt` | 3 |
| `data/remote/LocalNetworkClient.kt` | 3 |
| `data/repository/AuthRepository.kt` | 4 |
| `data/repository/DataRepository.kt` | 4 |
| `ConnectDemoApp.kt` | 5 |
| `di/AppModule.kt` | 5 |
| `ui/navigation/AppNavGraph.kt` | 6 |
| `ui/auth/LoginViewModel.kt` | 7 |
| `ui/auth/LoginScreen.kt` | 7 |
| `ui/home/HomeViewModel.kt` | 8 |
| `ui/home/HomeScreen.kt` | 8 |
| `MainActivity.kt` | 9 |
| `res/xml/network_security_config.xml` | 10 (if needed) |
| `ui/ocr/OcrScreen.kt` | 11 |
| `ui/sandbox/SandboxScreen.kt` | 11 |