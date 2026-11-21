package com.web2api.client

import com.web2api.client.exceptions.Web2ApiAuthException
import com.web2api.client.exceptions.Web2ApiExtensionUnavailableException
import com.web2api.client.models.ChatMessage
import com.web2api.client.models.ChatCompletionRequest
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class Web2ApiClientTest {

    private lateinit var server: MockWebServer
    private lateinit var client: Web2ApiClient

    @BeforeEach
    fun setUp() {
        server = MockWebServer()
        server.start()
        client = Web2ApiClient.Builder()
            .baseUrl(server.url("/").toString())
            .apiKey("test-key")
            .build()
    }

    @AfterEach
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun testHealthCheck() = runBlocking {
        val json = """
            {
                "status": "online",
                "extension_connected": true,
                "auth_required": true,
                "timestamp": "2026-11-22T00:00:00"
            }
        """.trimIndent()

        server.enqueue(MockResponse().setResponseCode(200).setBody(json))

        val health = client.checkHealth()
        assertEquals("online", health.status)
        assertTrue(health.extensionConnected)
        assertTrue(health.authRequired)
    }

    @Test
    fun testChatDirect() = runBlocking {
        val json = """
            {
                "response": "Hello from Android SDK test!",
                "latency_seconds": 1.25,
                "status": "success"
            }
        """.trimIndent()

        server.enqueue(MockResponse().setResponseCode(200).setBody(json))

        val answer = client.chat("Hello!")
        assertEquals("Hello from Android SDK test!", answer)

        val recorded = server.takeRequest()
        assertEquals("/api/chat", recorded.path)
        assertEquals("Bearer test-key", recorded.getHeader("Authorization"))
    }

    @Test
    fun testChatStreamFlow() = runBlocking {
        val sseBody = """
            data: {"id":"1","choices":[{"delta":{"role":"assistant"}}]}

            data: {"id":"1","choices":[{"delta":{"content":"Hello"}}]}

            data: {"id":"1","choices":[{"delta":{"content":" "}}]}

            data: {"id":"1","choices":[{"delta":{"content":"World!"}}]}

            data: [DONE]

        """.trimIndent()

        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "text/event-stream")
                .setBody(sseBody)
        )

        val chunks = client.chatStream("Hi").toList()
        assertEquals(listOf("Hello", " ", "World!"), chunks)
    }

    @Test
    fun testExtensionDisconnectedException() {
        server.enqueue(
            MockResponse()
                .setResponseCode(503)
                .setBody("""{"detail":"Browser Extension is not connected."}""")
        )

        assertFailsWith<Web2ApiExtensionUnavailableException> {
            runBlocking {
                client.chat("Hello")
            }
        }
    }

    @Test
    fun testUnauthorizedException() {
        server.enqueue(
            MockResponse()
                .setResponseCode(401)
                .setBody("""{"detail":"Unauthorized"}""")
        )

        assertFailsWith<Web2ApiAuthException> {
            runBlocking {
                client.chat("Hello")
            }
        }
    }
}
