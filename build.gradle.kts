// Top-level build file — plugin declarations only, no implementation config here.
// Each sub-project applies plugins via alias(libs.plugins.xxx)
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.hilt) apply false
}
