package com.yourapp.connectdemo.data.remote

import io.ktor.client.HttpClient
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.logging.LogLevel
import io.ktor.client.plugins.logging.Logger
import io.ktor.client.plugins.logging.Logging
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.HttpResponse
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.http.isSuccess
import io.ktor.serialization.kotlinx.json.json
import com.yourapp.connectdemo.util.Result

/**
 * Lightweight Ktor client for the "Test Connection" feature.
 * Sends a plain-text POST to a local network IP (configurable via BuildConfig.TARGET_IP).
 *
 * Lifecycle: provided as a @Singleton by Hilt (see AppModule.kt).
 * Call close() if you ever need to release the underlying connections (Hilt manages this).
 *
 * IMPORTANT — cleartext HTTP on Android 9+:
 * Sending to an http:// URL on API 28+ is blocked by default.
 * This project includes res/xml/network_security_config.xml that explicitly permits
 * cleartext traffic to local network IPs. Without it, this client throws:
 *   java.io.IOException: Cleartext HTTP traffic to 192.168.x.x not permitted
 */
class LocalNetworkClient {

    private val client = HttpClient(Android) {
        install(ContentNegotiation) {
            json()
        }
        install(Logging) {
            logger = object : Logger {
                override fun log(message: String) {
                    println("Ktor: $message")
                }
            }
            level  = LogLevel.BODY  // Use LogLevel.INFO in release builds
        }
        engine {
            connectTimeout = 10_000  // ms — increase if your local server is on a slow network
            socketTimeout  = 10_000
        }
    }

    /**
     * Sends [message] as a plain-text POST body to [targetUrl].
     *
     * Returns:
     *   Result.Success(responseBody) — server replied with 2xx
     *   Result.Error(message)        — network failure or non-2xx response
     *
     * All exceptions are caught — this never throws.
     */
    suspend fun sendHelloMessage(
        targetUrl: String,
        message: String
    ): Result<String> = try {
        val response: HttpResponse = client.post(targetUrl) {
            contentType(ContentType.Text.Plain)
            setBody(message)
        }
        if (response.status.isSuccess()) {
            Result.Success(response.bodyAsText())
        } else {
            Result.Error("Server returned HTTP ${response.status.value}: ${response.status.description}")
        }
    } catch (e: Exception) {
        Result.Error("Connection failed: ${e.localizedMessage ?: "Unknown error"}", e)
    }

    /** Release Ktor connections. Called automatically when Hilt destroys the singleton. */
    fun close() = client.close()
}
