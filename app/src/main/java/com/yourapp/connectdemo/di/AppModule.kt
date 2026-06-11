package com.yourapp.connectdemo.di

import com.yourapp.connectdemo.data.remote.LocalNetworkClient
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt DI module — provides dependencies that cannot be constructor-injected
 * (i.e. classes the app doesn't own, or that require factory setup).
 *
 * Note: AuthRepository and DataRepository use @Inject constructor directly,
 * so they don't need @Provides here.
 *
 * supabaseClient is a top-level lazy val (not Hilt-managed) because the Supabase SDK
 * uses a DSL builder that doesn't fit cleanly into Hilt's @Provides pattern.
 * This is an acceptable trade-off; the lazy + require() guards in SupabaseClient.kt
 * prevent misuse.
 */
@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideLocalNetworkClient(): LocalNetworkClient = LocalNetworkClient()
}
