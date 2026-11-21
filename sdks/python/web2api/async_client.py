"""
Asynchronous Web2API Client.
"""

import json
from typing import AsyncGenerator, Optional, Dict

try:
    import httpx
except ImportError:
    httpx = None

from .models import HealthStatus
from .exceptions import (
    Web2ApiException,
    Web2ApiAuthError,
    Web2ApiExtensionUnavailableError,
    Web2ApiTimeoutError,
    Web2ApiConnectionError,
)


class AsyncWeb2ApiClient:
    """
    Asynchronous client for communicating with a standalone Web2API server using httpx.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
        if httpx is None:
            raise ImportError("httpx is required for AsyncWeb2ApiClient. Install it via 'pip install httpx'.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self, content_type: str = "application/json") -> Dict[str, str]:
        headers = {"Content-Type": content_type, "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        return headers

    def _handle_status_code(self, code: int, body_text: str):
        if code == 401:
            raise Web2ApiAuthError()
        elif code == 503:
            raise Web2ApiExtensionUnavailableError()
        elif code == 504:
            raise Web2ApiTimeoutError()
        else:
            raise Web2ApiException(f"Server returned HTTP {code}: {body_text}", status_code=code)

    async def check_health(self) -> HealthStatus:
        """Checks server online and extension connection status asynchronously."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/health", headers=self._headers())
                if resp.status_code != 200:
                    self._handle_status_code(resp.status_code, resp.text)
                data = resp.json()
                return HealthStatus(
                    status=data.get("status", "unknown"),
                    extension_connected=data.get("extension_connected", False),
                    auth_required=data.get("auth_required", False),
                    timestamp=data.get("timestamp"),
                    stats=data.get("stats", {}),
                )
        except (Web2ApiException, Web2ApiAuthError):
            raise
        except Exception as e:
            raise Web2ApiConnectionError(f"Failed to connect to Web2API: {e}")

    async def chat(self, prompt: str, model: str = "gemini-pro") -> str:
        """
        Sends a simple prompt and returns the AI string response asynchronously.
        """
        payload = {"prompt": prompt, "model": model, "timeout": self.timeout}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload, headers=self._headers())
                if resp.status_code != 200:
                    self._handle_status_code(resp.status_code, resp.text)
                return resp.json().get("response", "")
        except (Web2ApiException, Web2ApiAuthError):
            raise
        except Exception as e:
            raise Web2ApiConnectionError(f"Error during async chat call: {e}")

    async def chat_stream(self, prompt: str, model: str = "gemini-pro") -> AsyncGenerator[str, None]:
        """
        Asynchronous real-time streaming generator using Server-Sent Events.
        """
        messages = [{"role": "user", "content": prompt}]
        payload = {"model": model, "messages": messages, "stream": True}
        headers = self._headers()
        headers["Accept"] = "text/event-stream"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}/v1/chat/completions", json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        self._handle_status_code(resp.status_code, body.decode("utf-8", errors="replace"))

                    async for line in resp.aiter_lines():
                        line_str = line.strip()
                        if line_str.startswith("data: "):
                            data_str = line_str[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
        except (Web2ApiException, Web2ApiAuthError):
            raise
        except Exception as e:
            raise Web2ApiConnectionError(f"Async streaming error: {e}")
