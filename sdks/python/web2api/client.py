"""
Synchronous Web2API Client.
"""

import json
from typing import Generator, List, Optional, Union, Dict, Any

try:
    import httpx
except ImportError:
    httpx = None

import urllib.request
import urllib.error

from .models import ChatMessage, ChatResponse, HealthStatus
from .exceptions import (
    Web2ApiException,
    Web2ApiAuthError,
    Web2ApiExtensionUnavailableError,
    Web2ApiTimeoutError,
    Web2ApiConnectionError,
)


class Web2ApiClient:
    """
    Synchronous client for communicating with a standalone Web2API server.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
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

    def check_health(self) -> HealthStatus:
        """Checks server online and extension connection status."""
        if httpx:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(f"{self.base_url}/health", headers=self._headers())
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

        # Fallback to standard library urllib
        req = urllib.request.Request(f"{self.base_url}/health", headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return HealthStatus(
                    status=data.get("status", "unknown"),
                    extension_connected=data.get("extension_connected", False),
                    auth_required=data.get("auth_required", False),
                    timestamp=data.get("timestamp"),
                    stats=data.get("stats", {}),
                )
        except urllib.error.HTTPError as e:
            self._handle_status_code(e.code, e.read().decode("utf-8", errors="replace"))
        except Exception as e:
            raise Web2ApiConnectionError(f"Failed to connect to Web2API: {e}")

    def chat(self, prompt: str, model: str = "gemini-pro") -> str:
        """
        Sends a simple prompt and returns the AI string response.
        """
        payload = {"prompt": prompt, "model": model, "timeout": self.timeout}
        if httpx:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(f"{self.base_url}/api/chat", json=payload, headers=self._headers())
                    if resp.status_code != 200:
                        self._handle_status_code(resp.status_code, resp.text)
                    return resp.json().get("response", "")
            except (Web2ApiException, Web2ApiAuthError):
                raise
            except Exception as e:
                raise Web2ApiConnectionError(f"Error during chat call: {e}")

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8")).get("response", "")
        except urllib.error.HTTPError as e:
            self._handle_status_code(e.code, e.read().decode("utf-8", errors="replace"))
        except Exception as e:
            raise Web2ApiConnectionError(f"Error during chat call: {e}")

    def chat_full(self, prompt: str, model: str = "gemini-pro") -> ChatResponse:
        """
        Sends a prompt and returns the full ChatResponse object including latency stats.
        """
        payload = {"prompt": prompt, "model": model, "timeout": self.timeout}
        if httpx:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(f"{self.base_url}/api/chat", json=payload, headers=self._headers())
                    if resp.status_code != 200:
                        self._handle_status_code(resp.status_code, resp.text)
                    data = resp.json()
                    return ChatResponse(
                        response=data.get("response", ""),
                        latency_seconds=data.get("latency_seconds", 0.0),
                        status=data.get("status", "success"),
                        extracted=data.get("extracted", {}),
                    )
            except (Web2ApiException, Web2ApiAuthError):
                raise
            except Exception as e:
                raise Web2ApiConnectionError(f"Error during chat_full call: {e}")

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return ChatResponse(
                    response=data.get("response", ""),
                    latency_seconds=data.get("latency_seconds", 0.0),
                    status=data.get("status", "success"),
                    extracted=data.get("extracted", {}),
                )
        except urllib.error.HTTPError as e:
            self._handle_status_code(e.code, e.read().decode("utf-8", errors="replace"))
        except Exception as e:
            raise Web2ApiConnectionError(f"Error during chat_full call: {e}")

    def chat_stream(self, prompt: str, model: str = "gemini-pro") -> Generator[str, None, None]:
        """
        Real-time Server-Sent Events (SSE) streaming generator.
        Yields text chunks as they are generated by the browser session.
        """
        messages = [{"role": "user", "content": prompt}]
        payload = {"model": model, "messages": messages, "stream": True}
        headers = self._headers()
        headers["Accept"] = "text/event-stream"

        if httpx:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    with client.stream("POST", f"{self.base_url}/v1/chat/completions", json=payload, headers=headers) as resp:
                        if resp.status_code != 200:
                            self._handle_status_code(resp.status_code, resp.read().decode("utf-8", errors="replace"))
                        for line in resp.iter_lines():
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
                return
            except (Web2ApiException, Web2ApiAuthError):
                raise
            except Exception as e:
                raise Web2ApiConnectionError(f"Streaming error: {e}")

        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
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
        except urllib.error.HTTPError as e:
            self._handle_status_code(e.code, e.read().decode("utf-8", errors="replace"))
        except Exception as e:
            raise Web2ApiConnectionError(f"Streaming error: {e}")

    def create_chat_completion(
        self,
        messages: List[Union[ChatMessage, Dict[str, str]]],
        model: str = "gemini-pro",
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Standard OpenAI-compatible Chat Completion endpoint.
        """
        formatted = []
        for m in messages:
            if isinstance(m, ChatMessage):
                formatted.append(m.to_dict())
            else:
                formatted.append(m)

        payload = {
            "model": model,
            "messages": formatted,
            "temperature": temperature,
            "stream": False,
        }

        if httpx:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(f"{self.base_url}/v1/chat/completions", json=payload, headers=self._headers())
                    if resp.status_code != 200:
                        self._handle_status_code(resp.status_code, resp.text)
                    return resp.json()
            except (Web2ApiException, Web2ApiAuthError):
                raise
            except Exception as e:
                raise Web2ApiConnectionError(f"Error during create_chat_completion call: {e}")

        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            self._handle_status_code(e.code, e.read().decode("utf-8", errors="replace"))
        except Exception as e:
            raise Web2ApiConnectionError(f"Error during create_chat_completion call: {e}")

    def reset_conversation(self) -> bool:
        """Resets the conversation tab in the active browser."""
        if httpx:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(f"{self.base_url}/api/reset", json={}, headers=self._headers())
                    if resp.status_code != 200:
                        self._handle_status_code(resp.status_code, resp.text)
                    return resp.json().get("status") == "success"
            except (Web2ApiException, Web2ApiAuthError):
                raise
            except Exception as e:
                raise Web2ApiConnectionError(f"Reset failed: {e}")

        req = urllib.request.Request(f"{self.base_url}/api/reset", data=b"{}", headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "success"
        except urllib.error.HTTPError as e:
            self._handle_status_code(e.code, e.read().decode("utf-8", errors="replace"))
        except Exception as e:
            raise Web2ApiConnectionError(f"Reset failed: {e}")
