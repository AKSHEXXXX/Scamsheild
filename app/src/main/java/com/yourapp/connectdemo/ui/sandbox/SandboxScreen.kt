package com.yourapp.connectdemo.ui.sandbox

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.yourapp.connectdemo.core.analytics.AnalyticsManager
import javax.inject.Inject

/**
 * Sandbox Feature — placeholder screen.
 *
 * Planned implementation:
 *   Isolated environment for evaluating potentially untrusted content received via
 *   the scam detection pipeline (e.g. suspicious URLs, message fragments).
 *   Options: sandboxed WebView with restrictive WebSettings, or a custom script runner.
 *
 * Route: Routes.SANDBOX — uncomment in Constants.kt and AppNavGraph.kt
 */
@Composable
fun SandboxScreen(
    analytics: AnalyticsManager = hiltViewModel()
) {
    LaunchedEffect(Unit) {
        analytics.screen("Sandbox")
    }
    Box(
        modifier        = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text  = "Sandbox — Coming Soon",
            style = MaterialTheme.typography.headlineMedium
        )
    }
}
