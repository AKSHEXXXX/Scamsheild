package com.yourapp.connectdemo

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.lifecycleScope
import androidx.navigation.compose.rememberNavController
import com.yourapp.connectdemo.data.remote.supabaseClient
import com.yourapp.connectdemo.data.repository.AuthRepository
import com.yourapp.connectdemo.ui.navigation.AppNavGraph
import com.yourapp.connectdemo.ui.theme.ConnectDemoTheme
import com.yourapp.connectdemo.util.Constants
import com.yourapp.connectdemo.util.Constants.Routes
import dagger.hilt.android.AndroidEntryPoint
import io.github.jan.supabase.gotrue.auth
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Entry point of the application.
 *
 * Two responsibilities:
 * 1. Determine the start destination (Login or Home) based on whether a session exists.
 * 2. Handle the OAuth deep-link callback via onNewIntent.
 *
 * Note on launchMode="singleTask" (set in AndroidManifest):
 * Required so that when the OAuth browser redirects back to this app, Android delivers
 * the intent to the EXISTING MainActivity instance via onNewIntent(), rather than creating
 * a new instance that would lose the current navigation state.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var authRepository: AuthRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val startDestination = if (supabaseClient.auth.currentUserOrNull() != null) {
            Routes.HOME
        } else {
            Routes.LOGIN
        }

        setContent {
            ConnectDemoTheme {
                val navController = rememberNavController()
                AppNavGraph(
                    navController    = navController,
                    startDestination = startDestination
                )
            }
        }
    }

    /**
     * Handles the OAuth deep-link intent after the browser completes authentication.
     *
     * FIX vs md spec: The original used runBlocking { ... } which blocks the main (UI) thread.
     * parseFragmentAndImportSession() makes a network call to exchange the auth code for a token.
     * On a slow connection this causes an ANR (Application Not Responding) dialog.
     *
     * Fix: lifecycleScope.launch{} — runs on the main dispatcher but suspends cooperatively,
     * never blocking the UI thread. The scope is automatically cancelled when the Activity
     * is destroyed, preventing coroutine leaks.
     *
     * After parseFragmentAndImportSession() returns:
     *   → supabaseClient.auth.sessionStatus emits Authenticated
     *   → LoginViewModel.isAuthenticated Flow emits true
     *   → LoginUiState.isSuccess = true
     *   → LaunchedEffect in LoginScreen navigates to HomeScreen
     */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        // setIntent is required with launchMode=singleTask so future getIntent() calls
        // return the new intent with the auth callback URI, not the original launch intent.
        setIntent(intent)

        val uri = intent.data?.toString() ?: return
        if (uri.startsWith(Constants.AUTH_CALLBACK_URI)) {
            lifecycleScope.launch {
                authRepository.handleAuthCallback(uri)
            }
        }
    }
}
