@file:OptIn(io.github.jan.supabase.annotations.SupabaseInternal::class)
package com.yourapp.connectdemo.data.repository

import com.yourapp.connectdemo.data.remote.supabaseClient
import com.yourapp.connectdemo.util.Result
import io.github.jan.supabase.gotrue.auth
import io.github.jan.supabase.gotrue.providers.Google
import io.github.jan.supabase.gotrue.providers.builtin.Email
import io.github.jan.supabase.gotrue.SessionStatus
import io.github.jan.supabase.gotrue.user.UserInfo
import io.github.jan.supabase.gotrue.parseFragmentAndImportSession
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Handles all authentication operations via Supabase Auth.
 *
 * IMPORTANT — OAuth flow is async, not synchronous:
 * signInWithGoogle() opens a Chrome Custom Tab. The user authenticates in the browser.
 * The browser then sends a deep-link intent back to MainActivity.onNewIntent().
 * MainActivity calls supabaseClient.auth.parseFragmentAndImportSession(uri) to import
 * the session token. ONLY THEN does sessionStatus emit Authenticated.
 *
 * ⚠️  Do NOT check isLoggedIn immediately after calling signInWithGoogle().
 *     Observe [isAuthenticated] Flow instead — it reacts to the actual session state change.
 *
 * No Android Context is accepted here — this is a pure repository.
 * The ViewModel layer (LoginViewModel extends AndroidViewModel) provides context when needed.
 */
@Singleton
class AuthRepository @Inject constructor() {

    val currentUser: UserInfo?
        get() = supabaseClient.auth.currentUserOrNull()

    val isLoggedIn: Boolean
        get() = currentUser != null

    /**
     * Reactive stream of whether the user is authenticated.
     * Emits true when a valid session exists (including after OAuth deep-link import).
     * Emits false after sign-out or session expiry.
     *
     * ViewModels should observe this Flow to drive navigation — not the return value
     * of signInWithGoogle(), which only tells you the browser was opened.
     */
    val isAuthenticated: Flow<Boolean> =
        supabaseClient.auth.sessionStatus.map { status ->
            status is SessionStatus.Authenticated
        }

    /**
     * Initiates the Google OAuth flow by opening a Chrome Custom Tab.
     *
     * This function returns after the tab opens — it does NOT wait for the user to authenticate.
     * Do NOT emit Result.Success from here (that was the md's bug — it caused premature navigation).
     * Real auth completion arrives via handleAuthCallback() → isAuthenticated Flow.
     */
    fun signInWithGoogle(): Flow<Result<Unit>> = flow {
        emit(Result.Loading)
        try {
            supabaseClient.auth.signInWith(Google) {
                // scheme/host come from Constants — kept in sync with SupabaseClient.kt and Manifest
            }
            // Emit Loading again (browser is now open, auth not complete yet).
            // The previous md version emitted Result.Success here — that was wrong.
            emit(Result.Loading)
        } catch (e: Exception) {
            emit(Result.Error("Failed to open Google sign-in: ${e.localizedMessage}", e))
        }
    }

    /**
     * Signs in a user using Email and Password.
     * Unlike OAuth, this flow completes synchronously on the network, so we emit Success
     * when the login call completes successfully.
     */
    fun signInWithEmail(emailAddress: String, passwordText: String): Flow<Result<Unit>> = flow {
        emit(Result.Loading)
        try {
            supabaseClient.auth.signInWith(Email) {
                email = emailAddress
                password = passwordText
            }
            emit(Result.Success(Unit))
        } catch (e: Exception) {
            emit(Result.Error("Sign in failed: ${e.localizedMessage}", e))
        }
    }

    /**
     * Registers a new user using Email and Password.
     */
    fun signUpWithEmail(emailAddress: String, passwordText: String): Flow<Result<Unit>> = flow {
        emit(Result.Loading)
        try {
            supabaseClient.auth.signUpWith(Email) {
                email = emailAddress
                password = passwordText
            }
            emit(Result.Success(Unit))
        } catch (e: Exception) {
            emit(Result.Error("Sign up failed: ${e.localizedMessage}", e))
        }
    }

    /**
     * Signs the current user out and clears the local session.
     * Observe the returned Flow for Success before navigating away from HomeScreen.
     */
    fun signOut(): Flow<Result<Unit>> = flow {
        emit(Result.Loading)
        try {
            supabaseClient.auth.signOut()
            emit(Result.Success(Unit))
        } catch (e: Exception) {
            emit(Result.Error("Sign out failed: ${e.localizedMessage}", e))
        }
    }

    /**
     * Called from MainActivity.onNewIntent() after the OAuth browser redirects back to the app.
     * This exchanges the auth code/fragment for a real session token and stores it locally.
     * After this completes, [isAuthenticated] will emit true.
     *
     * Must be called on a coroutine (suspend) — see MainActivity for lifecycleScope usage.
     */
    suspend fun handleAuthCallback(url: String) {
        supabaseClient.auth.parseFragmentAndImportSession(url)
    }
}
