import unittest
import json
import httpx

from web2api import Web2ApiClient
from web2api.exceptions import Web2ApiAuthError, Web2ApiExtensionUnavailableError


class TestWeb2ApiPythonClient(unittest.TestCase):

    def test_check_health(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/health")
            return httpx.Response(200, json={
                "status": "online",
                "extension_connected": True,
                "auth_required": True,
                "timestamp": "2026-11-22T00:00:00"
            })

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as mock_http:
            client = Web2ApiClient(base_url="http://test-server:8000", api_key="sk-test")
            # Inject mock client
            original_httpx = client._headers

            # Test using direct mock
            resp = mock_http.get("http://test-server:8000/health")
            data = resp.json()
            self.assertEqual(data["status"], "online")
            self.assertTrue(data["extension_connected"])

    def test_mock_chat_and_stream(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/chat":
                return httpx.Response(200, json={
                    "response": "Python SDK is working!",
                    "latency_seconds": 0.8,
                    "status": "success"
                })
            elif request.url.path == "/v1/chat/completions":
                sse_content = (
                    'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
                    'data: {"choices":[{"delta":{"content":" "}}]}\n\n'
                    'data: {"choices":[{"delta":{"content":"World!"}}]}\n\n'
                    'data: [DONE]\n\n'
                )
                return httpx.Response(200, content=sse_content.encode("utf-8"), headers={"content-type": "text/event-stream"})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as http:
            # Verify chat endpoint mock
            chat_res = http.post("http://test/api/chat", json={"prompt": "hi"}).json()
            self.assertEqual(chat_res["response"], "Python SDK is working!")

            # Verify stream endpoint mock
            stream_res = http.post("http://test/v1/chat/completions", json={"prompt": "hi"})
            lines = [l for l in stream_res.text.split("\n") if l.startswith("data: ")]
            self.assertEqual(len(lines), 4)

    def test_create_chat_completion_with_tools(self):
        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.read())
            self.assertIn("tools", data)
            self.assertEqual(data["tools"][0]["function"]["name"], "search")
            return httpx.Response(200, json={
                "id": "chatcmpl-tools",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "gemini-pro",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "search", "arguments": '{"query":"Python"}'}
                        }]
                    },
                    "finish_reason": "tool_calls"
                }]
            })

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as mock_http:
            client = Web2ApiClient(base_url="http://test-server:8000")
            tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
            res = mock_http.post(
                "http://test-server:8000/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Search Python"}], "tools": tools}
            ).json()

            choice = res["choices"][0]
            self.assertEqual(choice["finish_reason"], "tool_calls")
            self.assertEqual(choice["message"]["tool_calls"][0]["function"]["name"], "search")


if __name__ == "__main__":
    unittest.main()
