package com.web2api.client.models

import com.google.gson.annotations.SerializedName

/**
 * Single chat message representation.
 */
data class ChatMessage(
    @SerializedName("role") val role: String,
    @SerializedName("content") val content: String
) {
    companion object {
        fun user(content: String) = ChatMessage("user", content)
        fun assistant(content: String) = ChatMessage("assistant", content)
        fun system(content: String) = ChatMessage("system", content)
    }
}

/**
 * Standard OpenAI-compatible Chat Completion Request.
 */
data class ChatCompletionRequest(
    @SerializedName("model") val model: String = "gemini-pro",
    @SerializedName("messages") val messages: List<ChatMessage>,
    @SerializedName("temperature") val temperature: Double? = 0.7,
    @SerializedName("stream") val stream: Boolean? = false,
    @SerializedName("max_tokens") val maxTokens: Int? = null
)

/**
 * Chat completion response choice.
 */
data class ChatChoice(
    @SerializedName("index") val index: Int,
    @SerializedName("message") val message: ChatMessage?,
    @SerializedName("delta") val delta: ChatDelta?,
    @SerializedName("finish_reason") val finishReason: String?
)

/**
 * Streaming delta chunk payload.
 */
data class ChatDelta(
    @SerializedName("role") val role: String?,
    @SerializedName("content") val content: String?
)

/**
 * Standard OpenAI-compatible Chat Completion Response.
 */
data class ChatCompletionResponse(
    @SerializedName("id") val id: String,
    @SerializedName("object") val obj: String,
    @SerializedName("created") val created: Long,
    @SerializedName("model") val model: String,
    @SerializedName("choices") val choices: List<ChatChoice>,
    @SerializedName("latency_seconds") val latencySeconds: Double?
) {
    val text: String
        get() = choices.firstOrNull()?.message?.content ?: ""
}

/**
 * Simplified Direct Chat Response.
 */
data class Web2ApiChatResponse(
    @SerializedName("response") val response: String,
    @SerializedName("latency_seconds") val latencySeconds: Double,
    @SerializedName("status") val status: String
)

/**
 * Server and Browser Extension Health Status.
 */
data class HealthStatus(
    @SerializedName("status") val status: String,
    @SerializedName("extension_connected") val extensionConnected: Boolean,
    @SerializedName("auth_required") val authRequired: Boolean,
    @SerializedName("timestamp") val timestamp: String?
)

/**
 * List of available models.
 */
data class ModelListResponse(
    @SerializedName("object") val obj: String,
    @SerializedName("data") val data: List<ModelItem>
)

data class ModelItem(
    @SerializedName("id") val id: String,
    @SerializedName("owned_by") val ownedBy: String?
)
