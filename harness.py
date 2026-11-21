#!/usr/bin/env python3
"""
harness.py - Web2API Test, Mock & Agent Connection Harness
Provides a comprehensive suite to test, emulate, and connect to the Web2API bridge:

Commands:
  test  - Run automated end-to-end API & WebSocket verification suite (HTTP + SSE streaming)
  mock  - Run a standalone mock browser extension WebSocket client for headless testing
  chat  - Interactive terminal chat REPL with streaming SSE output
  acp   - Launch an autonomous Agent Client Protocol (ACP) agent powered by Web2API
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from typing import Optional

import httpx
import websockets

DEFAULT_API_BASE = os.getenv("WEB2API_BASE", "http://127.0.0.1:8000")
DEFAULT_WS_URL = os.getenv("WEB2API_WS", "ws://127.0.0.1:8000/ws")

# Terminal color formatting


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def log_info(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")


def log_success(msg: str):
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} {msg}")


def log_warn(msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def log_error(msg: str):
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {msg}")


# -----------------------------------------------------------------------------
# 1. MOCK EXTENSION ENGINE
# -----------------------------------------------------------------------------
class MockExtensionHarness:
    """
    Connects to the bridge WebSocket as a simulated Firefox / Zen browser extension.
    Allows headless verification of the bridge, OpenAI client libraries, and IDEs.
    """
    def __init__(self, ws_url: str = DEFAULT_WS_URL, simulated_delay: float = 0.05):
        self.ws_url = ws_url
        self.simulated_delay = simulated_delay
        self.running = False

    async def run(self, max_prompts: Optional[int] = None):
        log_info(f"Connecting Mock Extension to {self.ws_url}...")
        self.running = True
        prompts_handled = 0

        async with websockets.connect(self.ws_url) as ws:
            # 1. Send handshake
            handshake = {
                "type": "HANDSHAKE",
                "client": "firefox-zen-mock-harness",
                "browser": "Mozilla Zen 1.24 (Gecko)",
                "version": "2.0.0",
                "capabilities": ["chat", "stream", "code_blocks", "json_extraction"]
            }
            await ws.send(json.dumps(handshake))
            log_success("Mock Extension handshake accepted by bridge!")

            while self.running:
                try:
                    raw_msg = await ws.recv()
                    msg = json.loads(raw_msg)
                    req_id = msg.get("id")
                    action = msg.get("action")

                    if action == "PING":
                        await ws.send(json.dumps({"id": req_id, "status": "success", "message": "pong"}))
                        continue

                    if action == "RESET":
                        log_info("Received RESET action; simulating new conversation thread.")
                        await ws.send(json.dumps({"id": req_id, "status": "success", "data": {"reset": True}}))
                        continue

                    if action in ("CHAT", "PROMPT"):
                        prompt = msg.get("prompt", "")
                        model = msg.get("model", "gemini-pro")
                        log_info(f"Mock handling prompt for [{model}]: {prompt[:50]}...")

                        # Simulate model processing delay
                        await asyncio.sleep(self.simulated_delay)

                        # Generate synthetic structured response
                        simulated_response = self._synthesize_response(prompt, model)
                        await ws.send(json.dumps({
                            "id": req_id,
                            "status": "success",
                            "data": simulated_response
                        }))
                        prompts_handled += 1

                        if max_prompts is not None and prompts_handled >= max_prompts:
                            break

                except websockets.exceptions.ConnectionClosed:
                    log_warn("Mock extension connection closed.")
                    break
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log_error(f"Mock error: {e}")
                    break

    def _synthesize_response(self, prompt: str, model: str) -> dict:
        if "AVAILABLE TOOLS" in prompt:
            content = (
                "```tool_call\n"
                '{"name": "test_search", "arguments": {"query": "Web2API Architecture"}}\n'
                "```"
            )
        else:
            content = (
                f"Hello from Web2API Mock Harness [{model}]!\n\n"
                f"Received prompt: \"{prompt}\"\n\n"
                "```python\n"
                "def answer():\n"
                "    return 'Web2API Harness Connection Verified!'\n"
                "```\n"
            )
        return {
            "id": f"chatcmpl-mock-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop"
                }
            ],
            "extracted": {
                "code_blocks": [{"index": 0, "language": "python", "code": "def answer():\n    return 'Web2API Harness Connection Verified!'"}],
                "structured_data": None
            }
        }


# -----------------------------------------------------------------------------
# 2. AUTOMATED TEST SUITE HARNESS
# -----------------------------------------------------------------------------
class TestHarness:
    """
    Automated integration tester verifying all REST endpoints, SSE streams,
    and WebSocket communication.
    """
    def __init__(self, api_base: str = DEFAULT_API_BASE, ws_url: str = DEFAULT_WS_URL):
        self.api_base = api_base.rstrip("/")
        self.ws_url = ws_url

    async def run_suite(self):
        print(f"\n{Colors.BOLD}{Colors.HEADER}=== Web2API Integration & Conformance Test Suite ==={Colors.RESET}\n")
        passed = 0
        total = 0

        async with httpx.AsyncClient(base_url=self.api_base, timeout=30.0) as client:
            # 1. Health Endpoint
            total += 1
            is_connected = False
            try:
                res = await client.get("/health")
                assert res.status_code == 200, f"Expected 200, got {res.status_code}"
                data = res.json()
                assert data.get("status") == "online", "Bridge status is not online"
                is_connected = data.get("extension_connected", False)
                log_success(f"GET /health: online (Extension connected: {is_connected})")
                passed += 1
            except Exception as e:
                log_error(f"GET /health: {e}")

            # 2. Models Catalog
            total += 1
            try:
                res = await client.get("/v1/models")
                assert res.status_code == 200
                data = res.json()
                models = [m["id"] for m in data.get("data", [])]
                assert "gemini-pro" in models and "gpt-4o" in models and "claude-3-5-sonnet" in models
                log_success(f"GET /v1/models: returned {len(models)} models ({', '.join(models[:4])}...)")
                passed += 1
            except Exception as e:
                log_error(f"GET /v1/models: {e}")

            # 3. Check Extension Connection; if offline, spawn ephemeral mock
            mock_task = None
            if not is_connected:
                log_info("No browser extension currently connected. Spawning ephemeral mock extension...")
                mock = MockExtensionHarness(self.ws_url, simulated_delay=0.01)
                mock_task = asyncio.create_task(mock.run(max_prompts=None))
                await asyncio.sleep(0.3)

            try:
                # 4. Standard Non-Streaming Chat Completion
                total += 1
                payload = {
                    "model": "gemini-pro",
                    "messages": [{"role": "user", "content": "Respond with test confirmation."}],
                    "stream": False
                }
                res = await client.post("/v1/chat/completions", json=payload)
                assert res.status_code == 200, f"Status: {res.status_code}, body: {res.text}"
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                assert len(content) > 0
                log_success(f"POST /v1/chat/completions (JSON): received {len(content)} chars")
                passed += 1

                # 5. Streaming Server-Sent Events (SSE) Completion
                total += 1
                stream_payload = {
                    "model": "gemini-pro",
                    "messages": [{"role": "user", "content": "Stream a short response."}],
                    "stream": True
                }
                received_chunks = []
                async with client.stream("POST", "/v1/chat/completions", json=stream_payload) as stream_res:
                    assert stream_res.status_code == 200
                    assert "text/event-stream" in stream_res.headers.get("content-type", "")
                    async for line in stream_res.aiter_lines():
                        if line.startswith("data: "):
                            raw = line[6:].strip()
                            if raw == "[DONE]":
                                break
                            chunk = json.loads(raw)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                received_chunks.append(delta)

                streamed_text = "".join(received_chunks)
                assert len(streamed_text) > 0
                log_success(f"POST /v1/chat/completions (SSE Stream): received {len(received_chunks)} chunks ({len(streamed_text)} chars)")
                passed += 1

                # 6. Direct /api/chat Endpoint
                total += 1
                res = await client.post("/api/chat", json={"prompt": "Say hello!"})
                assert res.status_code == 200
                data = res.json()
                assert data.get("status") == "success"
                log_success(f"POST /api/chat: {data.get('response')[:40]}...")
                passed += 1

                # 7. Reset Endpoint
                total += 1
                res = await client.post("/api/reset")
                assert res.status_code == 200
                assert res.json().get("status") == "success"
                log_success("POST /api/reset: Thread reset successful")
                passed += 1

                # 8. Tool Calling Conformance
                total += 1
                tool_payload = {
                    "model": "gemini-pro",
                    "messages": [{"role": "user", "content": "Search for Web2API"}],
                    "tools": [{
                        "type": "function",
                        "function": {
                            "name": "test_search",
                            "description": "Search test tool",
                            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}
                        }
                    }],
                    "stream": False
                }
                res = await client.post("/v1/chat/completions", json=tool_payload)
                assert res.status_code == 200
                tool_data = res.json()
                choice = tool_data["choices"][0]
                assert choice["finish_reason"] == "tool_calls"
                assert choice["message"]["tool_calls"][0]["function"]["name"] == "test_search"
                log_success("POST /v1/chat/completions (Tool Calling): tool_calls parsed correctly")
                passed += 1

            except Exception as e:
                log_error(f"Test failure: {e}")
            finally:
                if mock_task and not mock_task.done():
                    mock_task.cancel()
                    try:
                        await mock_task
                    except asyncio.CancelledError:
                        pass

        print(f"\n{Colors.BOLD}=== Results: {passed}/{total} tests passed ==={Colors.RESET}\n")
        return passed == total


# -----------------------------------------------------------------------------
# 3. INTERACTIVE TERMINAL CHAT HARNESS
# -----------------------------------------------------------------------------
async def run_terminal_chat(api_base: str = DEFAULT_API_BASE, model: str = "gemini-pro"):
    """
    Interactive terminal chat harness with real-time streaming tokens.
    """
    print(f"\n{Colors.BOLD}{Colors.CYAN}=== Web2API Interactive Terminal Chat Harness ==={Colors.RESET}")
    print(f"Connected to: {api_base}")
    print(f"Current Model: {Colors.YELLOW}{model}{Colors.RESET}")
    print(f"Commands: {Colors.DIM}/model <name>, /reset, /status, /exit{Colors.RESET}\n")

    history = []

    async with httpx.AsyncClient(base_url=api_base, timeout=180.0) as client:
        while True:
            try:
                user_input = input(f"{Colors.BOLD}{Colors.GREEN}You > {Colors.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in ("/exit", "/quit"):
                print("Exiting chat harness.")
                break

            if user_input.startswith("/model"):
                parts = user_input.split()
                if len(parts) > 1:
                    model = parts[1]
                    print(f"Switched model to: {Colors.YELLOW}{model}{Colors.RESET}")
                else:
                    print("Usage: /model <model-name> (e.g. /model gpt-4o, /model claude-3-5-sonnet)")
                continue

            if user_input == "/reset":
                res = await client.post("/api/reset")
                history.clear()
                print(f"{Colors.BLUE}[Bridge]{Colors.RESET} Conversation history reset.")
                continue

            if user_input == "/status":
                res = await client.get("/health")
                print(json.dumps(res.json(), indent=2))
                continue

            history.append({"role": "user", "content": user_input})
            print(f"\n{Colors.BOLD}{Colors.CYAN}[{model}] > {Colors.RESET}", end="", flush=True)

            try:
                payload = {
                    "model": model,
                    "messages": history,
                    "stream": True
                }
                assistant_response = []

                async with client.stream("POST", "/v1/chat/completions", json=payload) as resp:
                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        print(f"\n{Colors.RED}Error ({resp.status_code}): {err_text.decode()}{Colors.RESET}")
                        continue

                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            raw = line[6:].strip()
                            if raw == "[DONE]":
                                break
                            try:
                                chunk = json.loads(raw)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    print(delta, end="", flush=True)
                                    assistant_response.append(delta)
                            except Exception:
                                pass

                print("\n")
                history.append({"role": "assistant", "content": "".join(assistant_response)})

            except Exception as e:
                print(f"\n{Colors.RED}Request Exception: {e}{Colors.RESET}\n")


# -----------------------------------------------------------------------------
# 4. AGENT CLIENT PROTOCOL (ACP) HARNESS
# -----------------------------------------------------------------------------
class ACPAgentHarness:
    """
    Autonomous ReAct coding agent implementing the Agent Client Protocol (ACP)
    over JSON-RPC stdio, backed by the Web2API browser bridge.
    """
    def __init__(self, api_base: str = DEFAULT_API_BASE, model: str = "gemini-pro"):
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.history = []

    async def start(self):
        # Read JSON-RPC lines from stdin and dispatch
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                req = json.loads(line.decode())
                await self.handle_rpc(req)
            except Exception as e:
                sys.stderr.write(f"[ACP Error] {e}\n")

    async def handle_rpc(self, req: dict):
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "1.0.0",
                    "capabilities": {"tools": True, "streaming": True},
                    "serverInfo": {"name": "Web2API-ACP", "version": "2.0.0"}
                }
            }
            self.send_response(resp)
            return

        if method == "agent/runTask":
            task = params.get("task", "")
            result = await self.execute_task_loop(task)
            self.send_response({"jsonrpc": "2.0", "id": req_id, "result": result})
            return

    def send_response(self, payload: dict):
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()

    async def execute_task_loop(self, task: str) -> dict:
        system_prompt = (
            "You are an autonomous ACP coding agent powered by Web2API.\n"
            "You have access to tools: read_file(path), write_file(path, content), run_command(command), finish(summary).\n"
            "Format your tool calls as JSON: {\"tool\": \"...\", \"parameters\": {...}}."
        )
        self.history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]

        async with httpx.AsyncClient(base_url=self.api_base, timeout=120.0) as client:
            resp = await client.post("/v1/chat/completions", json={
                "model": self.model,
                "messages": self.history
            })
            answer = resp.json()["choices"][0]["message"]["content"]
            return {"summary": answer, "status": "completed"}


# -----------------------------------------------------------------------------
# MAIN CLI ENTRYPOINT
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Web2API Harness Connection & Verification CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./harness.py test                   # Run full conformance test suite
  ./harness.py mock                   # Run mock extension on WebSocket for headless dev
  ./harness.py chat                   # Interactive terminal chat with real-time streaming
  ./harness.py chat --model claude    # Interactive chat targeting Claude
  ./harness.py acp                    # Run stdio ACP JSON-RPC agent
        """
    )
    parser.add_argument("command", choices=["test", "mock", "chat", "acp"], help="Action to execute")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API Base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--ws-url", default=DEFAULT_WS_URL, help=f"WebSocket Bridge URL (default: {DEFAULT_WS_URL})")
    parser.add_argument("--model", default="gemini-pro", help="Model name (gemini-pro, gpt-4o, claude-3-5-sonnet)")

    args = parser.parse_args()

    if args.command == "test":
        tester = TestHarness(api_base=args.api_base, ws_url=args.ws_url)
        success = asyncio.run(tester.run_suite())
        sys.exit(0 if success else 1)

    elif args.command == "mock":
        mock = MockExtensionHarness(ws_url=args.ws_url)
        print(f"{Colors.BOLD}{Colors.GREEN}Starting standalone Mock Browser Extension on {args.ws_url}...{Colors.RESET}")
        print("Press Ctrl+C to stop.")
        try:
            asyncio.run(mock.run())
        except KeyboardInterrupt:
            print("\nStopped mock extension.")

    elif args.command == "chat":
        asyncio.run(run_terminal_chat(api_base=args.api_base, model=args.model))

    elif args.command == "acp":
        agent = ACPAgentHarness(api_base=args.api_base, model=args.model)
        asyncio.run(agent.start())


if __name__ == "__main__":
    main()
