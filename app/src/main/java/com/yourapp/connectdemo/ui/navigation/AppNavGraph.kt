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
    NavHost(
        navController    = navController,
        startDestination = startDestination
    ) {

        composable(Routes.LOGIN) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Routes.HOME) {
                        // Remove Login from the back stack — pressing Back from Home exits the app
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.HOME) {
            HomeScreen(
                onLogout = {
                    navController.navigate(Routes.LOGIN) {
                        // Remove Home from the back stack — pressing Back from Login exits the app
                        popUpTo(Routes.HOME) { inclusive = true }
                    }
                }
            )
        }

        // Future routes — uncomment when features are implemented:
        // composable(Routes.OCR)     { OcrScreen() }
        // composable(Routes.SANDBOX) { SandboxScreen() }
    }
}
