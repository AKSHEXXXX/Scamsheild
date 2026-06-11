# Proguard rules for release build
# Supabase SDK
-keep class io.github.jan.supabase.** { *; }
# Ktor
-keep class io.ktor.** { *; }
# Kotlinx Serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-keep,includedescriptorclasses class com.yourapp.connectdemo.**$$serializer { *; }
-keepclassmembers class com.yourapp.connectdemo.** {
    *** Companion;
}
-keepclasseswithmembers class com.yourapp.connectdemo.** {
    kotlinx.serialization.KSerializer serializer(...);
}
