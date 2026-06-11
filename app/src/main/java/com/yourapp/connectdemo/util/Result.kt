package com.yourapp.connectdemo.util

/**
 * Sealed class representing the three states of any async operation.
 *
 * Usage pattern in ViewModels:
 *   when (result) {
 *       is Result.Loading -> showSpinner()
 *       is Result.Success -> showData(result.data)
 *       is Result.Error   -> showError(result.message)
 *   }
 */
sealed class Result<out T> {
    data class Success<T>(val data: T)                          : Result<T>()
    data class Error(val message: String, val cause: Throwable? = null) : Result<Nothing>()
    data object Loading                                          : Result<Nothing>()
}
