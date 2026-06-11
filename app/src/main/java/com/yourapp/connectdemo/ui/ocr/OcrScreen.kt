package com.yourapp.connectdemo.ui.ocr

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

/**
 * OCR Feature — placeholder screen.
 *
 * Planned implementation:
 *   1. Camera capture via CameraX
 *   2. ML Kit Text Recognition on captured frame
 *   3. POST recognised text to Supabase messages table via DataRepository.postMessage()
 *
 * Dependencies to add when implementing:
 *   implementation("com.google.mlkit:text-recognition:16.0.0")
 *   implementation("androidx.camera:camera-camera2:1.3.4")
 *   implementation("androidx.camera:camera-lifecycle:1.3.4")
 *   implementation("androidx.camera:camera-view:1.3.4")
 *
 * Route: Routes.OCR — uncomment in Constants.kt and AppNavGraph.kt
 */
@Composable
fun OcrScreen() {
    Box(
        modifier        = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text  = "OCR — Coming Soon",
            style = MaterialTheme.typography.headlineMedium
        )
    }
}
