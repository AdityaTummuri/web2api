"""
Integration tests for Tool Calling & Emulation on the Web2API Bridge Server.
"""

import json
import unittest
from fastapi.testclient import TestClient

from bridge_server import app, hub


class TestBridgeServerToolCalling(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        # Reset hub state before each test
        hub.active_socket = None
        hub.pending_requests.clear()

    def test_tool_calling_non_streaming(self):
        """
        Simulate extension sending a tool call fenced block and verify
        OpenAI-compatible tool_calls response.
        """
        # Mock active extension connection
        class MockWebSocket:
            def __init__(self):
                self.sent_messages = []

            async def send_text(self, text: str):
                self.sent_messages.append(text)
                payload = json.loads(text)
                req_id = payload.get("id")

                # Verify prompt contains tool schema
                prompt = payload.get("prompt", "")
                assert "AVAILABLE TOOLS" in prompt
                assert "get_stock_price" in prompt

                # Simulate model responding with a tool call block
                mock_tool_output = """
```tool_call
{"name": "get_stock_price", "arguments": {"ticker": "AAPL"}}
```
"""
                # Resolve request
                hub.resolve_response(req_id, {"text": mock_tool_output})

        mock_ws = MockWebSocket()
        hub.active_socket = mock_ws

        payload = {
            "model": "gemini-pro",
            "messages": [
                {"role": "user", "content": "What is the price of Apple stock?"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_stock_price",
                        "description": "Get current price for a stock ticker",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string"}
                            },
                            "required": ["ticker"]
                        }
                    }
                }
            ],
            "stream": False
        }

        resp = self.client.post("/v1/chat/completions", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["object"], "chat.completion")
        choices = data.get("choices", [])
        self.assertEqual(len(choices), 1)

        choice = choices[0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        message = choice["message"]
        self.assertIn("tool_calls", message)
        self.assertEqual(len(message["tool_calls"]), 1)

        tc = message["tool_calls"][0]
        self.assertEqual(tc["type"], "function")
        self.assertEqual(tc["function"]["name"], "get_stock_price")
        args = json.loads(tc["function"]["arguments"])
        self.assertEqual(args["ticker"], "AAPL")

    def test_tool_calling_streaming(self):
        """
        Simulate extension sending a tool call block under streaming mode
        and verify SSE chunks contain delta.tool_calls.
        """
        class MockWebSocket:
            async def send_text(self, text: str):
                payload = json.loads(text)
                req_id = payload.get("id")
                mock_tool_output = '```tool_call\n{"name": "calculate", "arguments": {"expr": "42 * 2"}}\n```'
                hub.resolve_response(req_id, {"text": mock_tool_output})

        hub.active_socket = MockWebSocket()

        payload = {
            "model": "gemini-pro",
            "messages": [
                {"role": "user", "content": "Calculate 42 times 2"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "calculate",
                        "description": "Evaluate math expression",
                        "parameters": {
                            "type": "object",
                            "properties": {"expr": {"type": "string"}},
                            "required": ["expr"]
                        }
                    }
                }
            ],
            "stream": True
        }

        resp = self.client.post("/v1/chat/completions", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/event-stream", resp.headers.get("content-type", ""))

        lines = resp.text.split("\n")
        data_lines = [line[6:].strip() for line in lines if line.startswith("data: ") and line[6:].strip() != "[DONE]"]

        tool_calls_seen = False
        finish_reason_seen = False

        for dl in data_lines:
            chunk = json.loads(dl)
            delta = chunk["choices"][0].get("delta", {})
            if "tool_calls" in delta:
                tool_calls_seen = True
            if chunk["choices"][0].get("finish_reason") == "tool_calls":
                finish_reason_seen = True

        self.assertTrue(tool_calls_seen)
        self.assertTrue(finish_reason_seen)

    def test_tool_continuation_turn(self):
        """
        Verify conversation continuation where client sends back the tool result.
        """
        class MockWebSocket:
            def __init__(self):
                self.sent_prompt = ""

            async def send_text(self, text: str):
                payload = json.loads(text)
                self.sent_prompt = payload.get("prompt", "")
                req_id = payload.get("id")
                # Assistant replies with normal conversation after tool result
                hub.resolve_response(req_id, {"text": "Apple stock is currently trading at $230.50."})

        mock_ws = MockWebSocket()
        hub.active_socket = mock_ws

        payload = {
            "model": "gemini-pro",
            "messages": [
                {"role": "user", "content": "What is the price of Apple stock?"},
                {
                    "role": "assistant",
                    "content": "Checking stock price...",
                    "tool_calls": [
                        {
                            "id": "call_aapl",
                            "type": "function",
                            "function": {"name": "get_stock_price", "arguments": '{"ticker": "AAPL"}'}
                        }
                    ]
                },
                {
                    "role": "tool",
                    "name": "get_stock_price",
                    "tool_call_id": "call_aapl",
                    "content": '{"price": 230.50, "currency": "USD"}'
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "get_stock_price", "parameters": {}}
                }
            ],
            "stream": False
        }

        resp = self.client.post("/v1/chat/completions", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        choice = data["choices"][0]
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertEqual(choice["message"]["content"], "Apple stock is currently trading at $230.50.")

        # Ensure prompt received by browser extension had the tool result turn formatted
        self.assertIn("Tool Result for `get_stock_price`", mock_ws.sent_prompt)
        self.assertIn('{"price": 230.50, "currency": "USD"}', mock_ws.sent_prompt)


if __name__ == "__main__":
    unittest.main()
