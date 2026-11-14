"""Unit tests for the Web2API Bridge Server."""

import unittest

from bridge_server import MessageItem, OpenAIChatRequest, Web2ApiRequest, app
from fastapi.testclient import TestClient


class TestBridgeServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("extension_connected", data)
        self.assertIn("stats", data)

    def test_status_endpoint(self):
        resp = self.client.get("/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "online")
        self.assertFalse(data["extension_connected"])

    def test_models_endpoint(self):
        resp = self.client.get("/v1/models")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["object"], "list")
        self.assertIsInstance(data["data"], list)
        model_ids = [m["id"] for m in data["data"]]
        self.assertIn("gemini-pro", model_ids)

    def test_chat_completions_no_extension(self):
        payload = {
            "model": "gemini-pro",
            "messages": [{"role": "user", "content": "Hello world"}],
        }
        resp = self.client.post("/v1/chat/completions", json=payload)
        self.assertEqual(resp.status_code, 503)
        data = resp.json()
        self.assertIn("Extension is not connected", data["detail"])

    def test_chat_completions_invalid_payload(self):
        payload = {
            "model": "gemini-pro"
            # Missing messages
        }
        resp = self.client.post("/v1/chat/completions", json=payload)
        self.assertEqual(resp.status_code, 422)

    def test_api_chat_no_extension(self):
        payload = {"prompt": "What is Web2API?"}
        resp = self.client.post("/api/chat", json=payload)
        self.assertEqual(resp.status_code, 503)

    def test_pydantic_models(self):
        msg = MessageItem(role="user", content="Ping")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Ping")

        req = OpenAIChatRequest(messages=[msg], model="gemini-1.5-pro", stream=False)
        self.assertEqual(req.model, "gemini-1.5-pro")
        self.assertFalse(req.stream)

        web_req = Web2ApiRequest(prompt="test prompt")
        self.assertEqual(web_req.prompt, "test prompt")


if __name__ == "__main__":
    unittest.main()
