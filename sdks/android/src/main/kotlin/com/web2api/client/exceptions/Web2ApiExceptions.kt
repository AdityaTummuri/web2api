package com.web2api.client.exceptions

/**
 * Base exception for all Web2API client errors.
 */
open class Web2ApiException(
    message: String,
    cause: Throwable? = null,
    val statusCode: Int? = null
) : Exception(message, cause)

/**
 * Thrown when the bridge server rejects authentication (HTTP 401).
 */
class Web2ApiAuthException(
    message: String = "Authentication failed. Provide a valid WEB2API_API_KEY in the client configuration."
) : Web2ApiException(message, statusCode = 401)

/**
 * Thrown when the browser extension is disconnected from the bridge server (HTTP 503).
 */
class Web2ApiExtensionUnavailableException(
    message: String = "Browser extension is not connected to the Web2API server. Ensure the browser is open and extension paired."
) : Web2ApiException(message, statusCode = 503)

/**
 * Thrown when an automated prompt response times out (HTTP 504).
 */
class Web2ApiTimeoutException(
    message: String = "The prompt request timed out waiting for the browser chat interface."
) : Web2ApiException(message, statusCode = 504)

/**
 * Thrown on network failure when connecting to the Web2API server.
 */
class Web2ApiNetworkException(
    message: String,
    cause: Throwable? = null
) : Web2ApiException(message, cause)
