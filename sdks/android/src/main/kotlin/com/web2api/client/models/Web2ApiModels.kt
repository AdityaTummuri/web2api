package com.web2api.client.models

import com.google.gson.annotations.SerializedName

/**
 * Tool call representation returned by the model.
 */
data class FunctionCall(
    @SerializedName("name") val name: String,
    @SerializedName("arguments") val arguments: String
)

data class ToolCall(
    @SerializedName("id") val id: String,
    @SerializedName("type") val type: String = "function",
    @SerializedName("function") val function: FunctionCall
)

/**
 * Tool definition provided to the model.
 */
data class FunctionDefinition(
    @SerializedName("name") val name: String,
    @SerializedName("description") val description: String? = null,
    @SerializedName("parameters") val parameters: Map<String, Any>? = null
)

data class Tool(
    @SerializedName("type") val type: String = "function",
    @SerializedName("function") val function: FunctionDefinition
)

/**
 * Single chat message representation.
 */
data class ChatMessage(
    @SerializedName("role") val role: String,
    @SerializedName("content") val content: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("tool_call_id") val toolCallId: String? = null,
    @SerializedName("tool_calls") val toolCalls: List<ToolCall>? = null
) {
    companion object {
        fun user(content: String) = ChatMessage("user", content)
        fun assistant(content: String) = ChatMessage("assistant", content)
        fun system(content: String) = ChatMessage("system", content)
        fun tool(toolCallId: String, name: String, content: String) =
            ChatMessage("tool", content = content, name = name, toolCallId = toolCallId)
    }
}

/**
 * Standard OpenAI-compatible Chat Completion Request with Tool Support.
 */
data class ChatCompletionRequest(
    @SerializedName("model") val model: String = "gemini-pro",
    @SerializedName("messages") val messages: List<ChatMessage>,
    @SerializedName("temperature") val temperature: Double? = 0.7,
    @SerializedName("stream") val stream: Boolean? = false,
    @SerializedName("max_tokens") val maxTokens: Int? = null,
    @SerializedName("tools") val tools: List<Tool>? = null,
    @SerializedName("tool_choice") val toolChoice: Any? = "auto"
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
    @SerializedName("content") val content: String?,
    @SerializedName("tool_calls") val toolCalls: List<ToolCall>? = null
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

    val toolCalls: List<ToolCall>
        get() = choices.firstOrNull()?.message?.toolCalls ?: emptyList()

    val isToolCall: Boolean
        get() = choices.firstOrNull()?.finishReason == "tool_calls"
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
