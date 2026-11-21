package com.web2api.client

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.web2api.client.exceptions.*
import com.web2api.client.models.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit

/**
 * Production-ready Web2API Client for Android / JVM.
 *
 * Connects to your standalone Web2API server to run AI prompts through
 * active browser sessions (ChatGPT, Claude, Gemini) with full streaming support.
 *
 * Example:
 * ```kotlin
 * val client = Web2ApiClient.Builder()
 *     .baseUrl("http://192.168.1.100:8000")
 *     .apiKey("sk-w2a-your-secret-key")
 *     .build()
 *
 * // One-shot prompt
 * val answer = client.chat("Summarize Android Coroutines in 3 bullet points")
 *
 * // Real-time token streaming
 * client.chatStream("Write a poem about Kotlin")
 *     .collect { chunk -> print(chunk) }
 * ```
 */
class Web2ApiClient private constructor(
    val baseUrl: String,
    val apiKey: String?,
    private val httpClient: OkHttpClient,
    private val gson: Gson
) {
    companion object {
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    }

    class Builder {
        private var baseUrl: String = "http://10.0.2.2:8000" // Default Android emulator host loopback
        private var apiKey: String? = null
        private var connectTimeoutSeconds: Long = 15
        private var readTimeoutSeconds: Long = 180
        private var customOkHttpClient: OkHttpClient? = null

        /**
         * Sets the base URL of your standalone Web2API bridge server.
         * For local emulator use: "http://10.0.2.2:8000"
         * For local physical device use your PC's LAN IP: "http://192.168.x.x:8000"
         * For remote VPS/cloud server: "https://api.yourdomain.com"
         */
        fun baseUrl(url: String) = apply {
            this.baseUrl = url.trimEnd('/')
        }

        /**
         * Sets the authentication API key (corresponds to WEB2API_API_KEY on the server).
         */
        fun apiKey(key: String?) = apply {
            this.apiKey = key
        }

        /**
         * Sets network timeouts.
         */
        fun timeouts(connectSec: Long = 15, readSec: Long = 180) = apply {
            this.connectTimeoutSeconds = connectSec
            this.readTimeoutSeconds = readSec
        }

        /**
         * Provide a custom OkHttpClient if needed.
         */
        fun client(client: OkHttpClient) = apply {
            this.customOkHttpClient = client
        }

        fun build(): Web2ApiClient {
            val client = customOkHttpClient ?: OkHttpClient.Builder()
                .connectTimeout(connectTimeoutSeconds, TimeUnit.SECONDS)
                .readTimeout(readTimeoutSeconds, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build()

            return Web2ApiClient(
                baseUrl = baseUrl,
                apiKey = apiKey,
                httpClient = client,
                gson = Gson()
            )
        }
    }

    /**
     * Checks if the Web2API server is online and whether the browser extension is connected.
     */
    suspend fun checkHealth(): HealthStatus = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$baseUrl/health")
            .get()
            .build()

        executeRequest(request) { body ->
            gson.fromJson(body, HealthStatus::class.java)
        }
    }

    /**
     * Sends a simple prompt string and returns the AI response text directly.
     *
     * @param prompt User prompt text.
     * @param model Target model (e.g., "gemini-pro", "gpt-4o", "claude-3-5-sonnet").
     * @return AI response string.
     */
    suspend fun chat(prompt: String, model: String = "gemini-pro"): String {
        val response = chatFull(prompt, model)
        return response.response
    }

    /**
     * Sends a simple prompt string and returns the full response object with latency stats.
     */
    suspend fun chatFull(prompt: String, model: String = "gemini-pro"): Web2ApiChatResponse =
        withContext(Dispatchers.IO) {
            val payload = JsonObject().apply {
                addProperty("prompt", prompt)
                addProperty("model", model)
                addProperty("timeout", 120.0)
            }

            val request = buildAuthenticatedRequest("$baseUrl/api/chat")
                .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
                .build()

            executeRequest(request) { body ->
                gson.fromJson(body, Web2ApiChatResponse::class.java)
            }
        }

    /**
     * Real-time streaming chat using Server-Sent Events (SSE) via Kotlin Flow.
     * Emits text chunks/tokens as they are generated by the browser AI session.
     *
     * @param prompt The prompt to execute.
     * @param model Target model (gemini-pro, gpt-4o, claude-3-5-sonnet).
     * @return Kotlin Flow emitting real-time text chunks.
     */
    fun chatStream(prompt: String, model: String = "gemini-pro"): Flow<String> = callbackFlow {
        val requestPayload = ChatCompletionRequest(
            model = model,
            messages = listOf(ChatMessage.user(prompt)),
            stream = true
        )

        val request = buildAuthenticatedRequest("$baseUrl/v1/chat/completions")
            .post(gson.toJson(requestPayload).toRequestBody(JSON_MEDIA_TYPE))
            .build()

        val call = httpClient.newCall(request)

        try {
            val response = call.execute()
            if (!response.isSuccessful) {
                val errorBody = response.body?.string().orEmpty()
                handleHttpError(response.code, errorBody)
            }

            val source = response.body?.byteStream()
            if (source == null) {
                close(Web2ApiException("Streaming response body is null"))
                return@callbackFlow
            }

            val reader = BufferedReader(InputStreamReader(source))
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                val currentLine = line?.trim() ?: continue
                if (currentLine.startsWith("data: ")) {
                    val data = currentLine.removePrefix("data: ").trim()
                    if (data == "[DONE]") {
                        break
                    }
                    try {
                        val chunkObj = gson.fromJson(data, JsonObject::class.java)
                        val choices = chunkObj.getAsJsonArray("choices")
                        if (choices != null && choices.size() > 0) {
                            val firstChoice = choices.get(0).asJsonObject
                            val delta = firstChoice.getAsJsonObject("delta")
                            if (delta != null && delta.has("content")) {
                                val token = delta.get("content").asString
                                trySend(token)
                            }
                        }
                    } catch (e: Exception) {
                        // Skip malformed SSE chunks
                    }
                }
            }
            close()
        } catch (e: IOException) {
            close(Web2ApiNetworkException("Network error during SSE stream: ${e.message}", e))
        } catch (e: Exception) {
            close(e)
        }

        awaitClose {
            call.cancel()
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Executes standard OpenAI-compatible Chat Completions.
     */
    suspend fun createChatCompletion(request: ChatCompletionRequest): ChatCompletionResponse =
        withContext(Dispatchers.IO) {
            val httpRequest = buildAuthenticatedRequest("$baseUrl/v1/chat/completions")
                .post(gson.toJson(request).toRequestBody(JSON_MEDIA_TYPE))
                .build()

            executeRequest(httpRequest) { body ->
                gson.fromJson(body, ChatCompletionResponse::class.java)
            }
        }

    /**
     * Resets the active conversation tab in the browser.
     */
    suspend fun resetConversation(): Boolean = withContext(Dispatchers.IO) {
        val request = buildAuthenticatedRequest("$baseUrl/api/reset")
            .post("{}".toRequestBody(JSON_MEDIA_TYPE))
            .build()

        executeRequest(request) { body ->
            val obj = gson.fromJson(body, JsonObject::class.java)
            obj.get("status")?.asString == "success"
        }
    }

    /**
     * Lists available models on the server.
     */
    suspend fun listModels(): List<ModelItem> = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$baseUrl/v1/models")
            .get()
            .build()

        executeRequest(request) { body ->
            val res = gson.fromJson(body, ModelListResponse::class.java)
            res.data
        }
    }

    private fun buildAuthenticatedRequest(url: String): Request.Builder {
        val builder = Request.Builder().url(url)
        if (!apiKey.isNullOrBlank()) {
            builder.addHeader("Authorization", "Bearer $apiKey")
            builder.addHeader("X-API-Key", apiKey)
        }
        return builder
    }

    private inline fun <T> executeRequest(request: Request, parser: (String) -> T): T {
        try {
            val response = httpClient.newCall(request).execute()
            val bodyString = response.body?.string().orEmpty()

            if (!response.isSuccessful) {
                handleHttpError(response.code, bodyString)
            }

            return parser(bodyString)
        } catch (e: Web2ApiException) {
            throw e
        } catch (e: IOException) {
            throw Web2ApiNetworkException("Connection to Web2API failed: ${e.message}", e)
        } catch (e: Exception) {
            throw Web2ApiException("Unexpected error calling Web2API: ${e.message}", e)
        }
    }

    private fun handleHttpError(statusCode: Int, body: String) {
        when (statusCode) {
            401 -> throw Web2ApiAuthException()
            503 -> throw Web2ApiExtensionUnavailableException()
            504 -> throw Web2ApiTimeoutException()
            else -> throw Web2ApiException("Web2API Error (HTTP $statusCode): $body", statusCode = statusCode)
        }
    }
}
