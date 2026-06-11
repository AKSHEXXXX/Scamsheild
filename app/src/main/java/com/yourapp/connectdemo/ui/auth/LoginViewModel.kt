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
    val email: String = "",
    val password: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
    val isSuccess: Boolean = false,
    val isSignUpMode: Boolean = false,
    val isPasswordVisible: Boolean = false
)

/**
 * ViewModel for the Login screen.
 *
 * Extends AndroidViewModel (not plain ViewModel) so we can access Application context
 * without violating clean architecture by passing Context into the repository layer.
 * Currently Application context isn't actively used, but it's available if needed for
 * future features (e.g. custom Chrome Custom Tab configuration).
 *
 * Key design: isSuccess is driven by observing [AuthRepository.isAuthenticated] Flow,
 * NOT by the return value of signInWithGoogle().
 * Reason: signInWithGoogle() only opens a browser tab — it returns before auth completes.
 * The actual session is established asynchronously via the deep-link OAuth callback,
 * after which sessionStatus emits Authenticated, which triggers isSuccess = true here.
 */
@HiltViewModel
class LoginViewModel @Inject constructor(
    application: Application,
    private val authRepository: AuthRepository
) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    init {
        // Observe the real Supabase session state.
        // This fires when MainActivity.onNewIntent() calls handleAuthCallback()
        // and parseFragmentAndImportSession() successfully stores the token.
        authRepository.isAuthenticated
            .onEach { authenticated ->
                if (authenticated) {
                    _uiState.value = _uiState.value.copy(isSuccess = true, isLoading = false)
                }
            }
            .launchIn(viewModelScope)
    }

    fun onEmailChanged(email: String) {
        _uiState.value = _uiState.value.copy(email = email)
    }

    fun onPasswordChanged(password: String) {
        _uiState.value = _uiState.value.copy(password = password)
    }

    fun toggleSignUpMode() {
        _uiState.value = _uiState.value.copy(
            isSignUpMode = !_uiState.value.isSignUpMode,
            error = null
        )
    }

    fun togglePasswordVisibility() {
        _uiState.value = _uiState.value.copy(isPasswordVisible = !_uiState.value.isPasswordVisible)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    /**
     * Starts the Google OAuth flow by opening a Chrome Custom Tab.
     * After this returns, the user is in the browser — auth is NOT complete.
     * Navigation to Home happens via the isAuthenticated Flow observer in init{}.
     */
    fun signInWithGoogle() {
        authRepository.signInWithGoogle()
            .onEach { result ->
                when (result) {
                    // Loading = "browser tab is opening" — show spinner
                    is Result.Loading -> _uiState.value = _uiState.value.copy(isLoading = true, error = null)
                    // Success is never emitted by signInWithGoogle() (by design).
                    // Real success comes through the isAuthenticated Flow observer above.
                    is Result.Success -> { /* handled by isAuthenticated observer in init{} */ }
                    is Result.Error   -> _uiState.value = _uiState.value.copy(isLoading = false, error = result.message)
                }
            }
            .launchIn(viewModelScope)
    }

    /**
     * Signs in a user using Email and Password.
     */
    fun signInWithEmail() {
        val currentState = _uiState.value
        if (currentState.email.isBlank() || currentState.password.isBlank()) {
            _uiState.value = currentState.copy(error = "Email and password cannot be blank.")
            return
        }

        authRepository.signInWithEmail(currentState.email.trim(), currentState.password)
            .onEach { result ->
                when (result) {
                    is Result.Loading -> _uiState.value = _uiState.value.copy(isLoading = true, error = null)
                    is Result.Success -> {
                        // Handled by isAuthenticated observer, but safe to set success here too
                        _uiState.value = _uiState.value.copy(isLoading = false, isSuccess = true)
                    }
                    is Result.Error   -> _uiState.value = _uiState.value.copy(isLoading = false, error = result.message)
                }
            }
            .launchIn(viewModelScope)
    }

    /**
     * Registers a new user using Email and Password.
     */
    fun signUpWithEmail() {
        val currentState = _uiState.value
        if (currentState.email.isBlank() || currentState.password.isBlank()) {
            _uiState.value = currentState.copy(error = "Email and password cannot be blank.")
            return
        }
        if (currentState.password.length < 6) {
            _uiState.value = currentState.copy(error = "Password must be at least 6 characters.")
            return
        }

        authRepository.signUpWithEmail(currentState.email.trim(), currentState.password)
            .onEach { result ->
                when (result) {
                    is Result.Loading -> _uiState.value = _uiState.value.copy(isLoading = true, error = null)
                    is Result.Success -> {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = "Registration successful! If verification is enabled, check your email."
                        )
                    }
                    is Result.Error   -> _uiState.value = _uiState.value.copy(isLoading = false, error = result.message)
                }
            }
            .launchIn(viewModelScope)
    }
}
