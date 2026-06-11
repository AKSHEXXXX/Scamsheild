package com.yourapp.connectdemo.data.repository

import com.yourapp.connectdemo.BuildConfig
import com.yourapp.connectdemo.data.model.MessageModel
import com.yourapp.connectdemo.data.remote.LocalNetworkClient
import com.yourapp.connectdemo.data.remote.supabaseClient
import com.yourapp.connectdemo.util.Constants
import com.yourapp.connectdemo.util.Result
import io.github.jan.supabase.gotrue.auth
import io.github.jan.supabase.postgrest.postgrest
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Data repository — single source of truth for:
 *   1. Local network "Test Connection" (via LocalNetworkClient)
 *   2. Supabase PostgREST CRUD operations (messages table)
 *
 * All functions return Flow<Result<T>> — never throws, always wraps exceptions in Result.Error.
 */
@Singleton
class DataRepository @Inject constructor(
    private val localNetworkClient: LocalNetworkClient
) {

    // ── Local Network (Test Connection) ──────────────────────────────────────────

    /**
     * Sends "Hello from Android" to the configured local IP address.
     * The TARGET_IP BuildConfig field must be set in build.gradle.kts.
     * Cleartext (http://) is permitted for local IPs via network_security_config.xml.
     */
    fun sendTestMessage(): Flow<Result<String>> = flow {
        emit(Result.Loading)
        val result = localNetworkClient.sendHelloMessage(
            targetUrl = BuildConfig.TARGET_IP,
            message   = Constants.TEST_MESSAGE
        )
        emit(result)
    }

    // ── Supabase: POST ────────────────────────────────────────────────────────────

    /**
     * Inserts [content] as a new message row into the `messages` table.
     * Requires the user to be authenticated (Supabase RLS enforces this server-side).
     */
    fun postMessage(content: String): Flow<Result<Unit>> = flow {
        emit(Result.Loading)
        try {
            val userId = supabaseClient.auth.currentUserOrNull()?.id
                ?: throw Exception("User not authenticated — cannot post message")

            supabaseClient.postgrest["messages"].insert(
                MessageModel(content = content, userId = userId)
            )
            emit(Result.Success(Unit))
        } catch (e: Exception) {
            emit(Result.Error("Post failed: ${e.localizedMessage}", e))
        }
    }

    // ── Supabase: GET ─────────────────────────────────────────────────────────────

    /**
     * Fetches all messages from the `messages` table.
     * Supabase RLS policy requires the user to be authenticated.
     */
    fun getMessages(): Flow<Result<List<MessageModel>>> = flow {
        emit(Result.Loading)
        try {
            val messages = supabaseClient.postgrest["messages"]
                .select()
                .decodeList<MessageModel>()
            emit(Result.Success(messages))
        } catch (e: Exception) {
            emit(Result.Error("Fetch failed: ${e.localizedMessage}", e))
        }
    }
}
