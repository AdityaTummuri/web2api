"""
Web2API Python Client Library
Official client library for connecting to standalone Web2API servers.
"""

from .client import Web2ApiClient
from .async_client import AsyncWeb2ApiClient
from .models import ChatMessage, ChatResponse, HealthStatus
from .exceptions import (
    Web2ApiException,
    Web2ApiAuthError,
    Web2ApiExtensionUnavailableError,
    Web2ApiTimeoutError,
    Web2ApiConnectionError,
)

__version__ = "2.0.0"
__all__ = [
    "Web2ApiClient",
    "AsyncWeb2ApiClient",
    "ChatMessage",
    "ChatResponse",
    "HealthStatus",
    "Web2ApiException",
    "Web2ApiAuthError",
    "Web2ApiExtensionUnavailableError",
    "Web2ApiTimeoutError",
    "Web2ApiConnectionError",
]
