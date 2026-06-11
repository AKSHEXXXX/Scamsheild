package com.yourapp.connectdemo.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Maps to the `messages` table in Supabase.
 *
 * SQL schema (run in Supabase SQL Editor before first launch):
 *   CREATE TABLE messages (
 *       id         BIGSERIAL PRIMARY KEY,
 *       content    TEXT NOT NULL,
 *       user_id    UUID REFERENCES auth.users(id),
 *       created_at TIMESTAMPTZ DEFAULT NOW()
 *   );
 *   ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
 *   CREATE POLICY "insert_own" ON messages FOR INSERT TO authenticated
 *       WITH CHECK (auth.uid() = user_id);
 *   CREATE POLICY "read_all"   ON messages FOR SELECT TO authenticated
 *       USING (true);
 *
 * @Serializable requires:
 *   - kotlin-serialization Gradle plugin in build.gradle.kts
 *   - kotlinx-serialization-json runtime dependency
 *   Both are included in this project's configuration.
 */
@Serializable
data class MessageModel(
    val id: Long? = null,
    val content: String,
    @SerialName("created_at")
    val createdAt: String? = null,
    @SerialName("user_id")
    val userId: String? = null
)
