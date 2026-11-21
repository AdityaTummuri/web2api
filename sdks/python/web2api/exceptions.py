"""
Exceptions for Web2API Python SDK.
"""


class Web2ApiException(Exception):
    """Base exception for Web2API SDK errors."""
    def __init__(self, message: str, status_code: int = None, details: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class Web2ApiAuthError(Web2ApiException):
    """Raised when authentication fails (HTTP 401)."""
    def __init__(self, message: str = "Invalid or missing Web2API API Key."):
        super().__init__(message, status_code=401)


class Web2ApiExtensionUnavailableError(Web2ApiException):
    """Raised when the browser extension is disconnected from the bridge (HTTP 503)."""
    def __init__(self, message: str = "Browser extension is not connected to Web2API server."):
        super().__init__(message, status_code=503)


class Web2ApiTimeoutError(Web2ApiException):
    """Raised when an automated prompt response times out (HTTP 504)."""
    def __init__(self, message: str = "Prompt request timed out waiting for browser AI response."):
        super().__init__(message, status_code=504)


class Web2ApiConnectionError(Web2ApiException):
    """Raised on network failure connecting to the Web2API server."""
    pass
