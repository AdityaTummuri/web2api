package com.web2api.client.sample

import com.web2api.client.Web2ApiClient
import com.web2api.client.models.ChatMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Example UI State and ViewModel for an Android app using Web2API.
 *
 * Demonstrates:
 * 1. Initializing Web2ApiClient pointing to your remote server or local emulator.
 * 2. Streaming responses into real-time UI text using Kotlin Flow.
 * 3. Handling extension disconnection and error states.
 */
data class UiMessage(
    val sender: String,
    val text: String,
    val isStreaming: Boolean = false
)

class Web2ApiChatViewModel(
    serverBaseUrl: String = "http://10.0.2.2:8000",
    apiKey: String? = null
) {
    private val client = Web2ApiClient.Builder()
        .baseUrl(serverBaseUrl)
        .apiKey(apiKey)
        .build()

    private val viewModelScope = CoroutineScope(Dispatchers.Main)

    private val _messages = MutableStateFlow<List<UiMessage>>(emptyList())
    val messages = _messages.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading = _isLoading.asStateFlow()

    private val _serverStatus = MutableStateFlow("Checking...")
    val serverStatus = _serverStatus.asStateFlow()

    init {
        checkServerHealth()
    }

    fun checkServerHealth() {
        viewModelScope.launch {
            try {
                val health = client.checkHealth()
                _serverStatus.value = if (health.extensionConnected) {
                    "Connected (${health.status})"
                } else {
                    "Server online, Extension disconnected"
                }
            } catch (e: Exception) {
                _serverStatus.value = "Server unreachable: ${e.message}"
            }
        }
    }

    /**
     * Sends a message with real-time token streaming.
     */
    fun sendMessage(userPrompt: String, model: String = "gemini-pro") {
        if (userPrompt.isBlank()) return

        val currentList = _messages.value.toMutableList()
        currentList.add(UiMessage(sender = "User", text = userPrompt))

        val assistantIndex = currentList.size
        currentList.add(UiMessage(sender = "Assistant", text = "", isStreaming = true))
        _messages.value = currentList
        _isLoading.value = true

        viewModelScope.launch {
            try {
                val responseBuilder = StringBuilder()
                client.chatStream(userPrompt, model = model).collect { chunk ->
                    responseBuilder.append(chunk)
                    val updated = _messages.value.toMutableList()
                    if (assistantIndex < updated.size) {
                        updated[assistantIndex] = UiMessage(
                            sender = "Assistant",
                            text = responseBuilder.toString(),
                            isStreaming = true
                        )
                        _messages.value = updated
                    }
                }

                // Finalize streaming
                val finalUpdated = _messages.value.toMutableList()
                if (assistantIndex < finalUpdated.size) {
                    finalUpdated[assistantIndex] = finalUpdated[assistantIndex].copy(isStreaming = false)
                    _messages.value = finalUpdated
                }
            } catch (e: Exception) {
                val errorList = _messages.value.toMutableList()
                if (assistantIndex < errorList.size) {
                    errorList[assistantIndex] = UiMessage(
                        sender = "Assistant",
                        text = "Error: ${e.message}",
                        isStreaming = false
                    )
                    _messages.value = errorList
                }
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun resetChat() {
        viewModelScope.launch {
            try {
                client.resetConversation()
                _messages.value = emptyList()
            } catch (e: Exception) {
                // handle error
            }
        }
    }
}
