package com.yourapp.connectdemo.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yourapp.connectdemo.data.model.MessageModel
import com.yourapp.connectdemo.data.repository.AuthRepository
import com.yourapp.connectdemo.data.repository.DataRepository
import com.yourapp.connectdemo.util.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HomeUiState(
    val isLoading: Boolean = false,
    val connectionStatus: String? = null,
    val messages: List<MessageModel> = emptyList(),
    val error: String? = null,
    val postSuccess: Boolean = false,
    // isLoggedOut drives navigation from state (not from a fire-and-forget onClick)
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

    // ── Test Connection ───────────────────────────────────────────────────────────

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

    // ── Supabase GET ──────────────────────────────────────────────────────────────

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

    // ── Supabase POST ─────────────────────────────────────────────────────────────

    /**
     * Posts [content] to the database.
     *
     * FIX: The md spec called fetchMessages() synchronously inside the Success handler.
     * Problem: fetchMessages() immediately sets isLoading = true, overwriting postSuccess = true
     * before LaunchedEffect in HomeScreen can react to clear the text field.
     *
     * Fix: Set postSuccess first, then launch fetchMessages() in a separate coroutine.
     * This allows the current composition frame to react to postSuccess = true first.
     */
    fun postToDatabase(content: String) {
        dataRepository.postMessage(content)
            .onEach { result ->
                when (result) {
                    is Result.Loading -> _uiState.value = _uiState.value.copy(isLoading = true)
                    is Result.Success -> {
                        _uiState.value = _uiState.value.copy(
                            isLoading   = false,
                            postSuccess = true
                        )
                        // Fetch in a separate coroutine so postSuccess = true is observed first
                        viewModelScope.launch { fetchMessages() }
                    }
                    is Result.Error -> _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error     = result.message
                    )
                }
            }
            .launchIn(viewModelScope)
    }

    // ── Sign Out ──────────────────────────────────────────────────────────────────

    /**
     * Signs out the user.
     *
     * FIX: The md spec called onLogout() synchronously inside the IconButton onClick,
     * which meant the app navigated to Login BEFORE sign-out completed — leaving an active
     * Supabase session in memory while showing the Login screen.
     *
     * Fix: signOut() here only triggers the async operation.
     * Navigation is driven by isLoggedOut = true in the state, observed by LaunchedEffect
     * in HomeScreen — which only fires AFTER Result.Success is received from signOut().
     */
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
                        error     = "Sign out failed: ${result.message}"
                    )
                }
            }
            .launchIn(viewModelScope)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
