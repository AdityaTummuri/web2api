"""
bridge_server.py - Web2API Universal Bridge Server
Exposes an OpenAI-compatible REST API (and Web2API endpoints) that routes
requests directly into an authenticated browser session (Chrome, Firefox, Zen, etc.) via WebSocket.
Can be run locally or deployed independently on any remote server / container.
"""

import asyncio
import hmac
import ipaddress
import json
import logging
import os
import re
import socket
import sys
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from tool_parser import format_conversation_with_tools, parse_tool_calls
from web2api_keys import keys_file_path, load_keys, redeem_pairing_code

# Configuration
# Loopback by default: exposing the bridge on a network is an explicit opt-in.
# HOST may list several addresses, e.g. HOST=127.0.0.1,100.101.102.103 listens on
# loopback (for the local browser) plus the Tailscale address only, not on Wi-Fi/LAN.
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [orig.strip() for orig in CORS_ORIGINS_RAW.split(",") if orig.strip()] or ["*"]

TOKEN_IN_URL = re.compile(r"((?:token|key)=)[^&\s\"']+", re.IGNORECASE)
KEY_IN_TEXT = re.compile(r"sk-w2a-[A-Za-z0-9_-]{8,}")


class RedactTokensFilter(logging.Filter):
    """Mask ?token=/?key= values so API keys never end up in uvicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.args = tuple(
                TOKEN_IN_URL.sub(r"\1***", a) if isinstance(a, str) else a for a in record.args
            )
        if isinstance(record.msg, str):
            record.msg = TOKEN_IN_URL.sub(r"\1***", record.msg)
        return True


for _logger_name in ("uvicorn.access", "uvicorn.error", "uvicorn"):
    logging.getLogger(_logger_name).addFilter(RedactTokensFilter())

app = FastAPI(
    title="Web2API Universal Bridge Server",
    description="Transforms active browser AI chat sessions into a high-speed OpenAI-compatible REST & WebSocket API.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_allowed_api_keys() -> set:
    """Returns the set of accepted API keys (WEB2API_API_KEY env var + api.txt)."""
    return set(load_keys())


def auth_required() -> bool:
    """Auth is enforced whenever any key is configured (or WEB2API_REQUIRE_AUTH is set)."""
    if get_allowed_api_keys():
        return True
    return os.getenv("WEB2API_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")


def is_valid_key(provided: Optional[str]) -> bool:
    if not provided:
        return False
    return any(hmac.compare_digest(provided.encode(), k.encode()) for k in get_allowed_api_keys())


async def verify_api_key(request: Request):
    """
    API Key verification. Checks the WEB2API_API_KEY env var and api.txt.
    Accepts 'Authorization: Bearer <key>' or 'X-API-Key: <key>'.
    Once any key is configured, every request must carry a valid key.
    """
    auth_header = request.headers.get("authorization", "")
    token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else None
    provided_key = token or request.headers.get("x-api-key")

    if not auth_required():
        return True

    if not is_valid_key(provided_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing API key. Provide 'Authorization: Bearer <KEY>' or 'X-API-Key: <KEY>'.",
        )
    return True


def is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_startup_security(host: str) -> Optional[str]:
    """Returns an error message if it is unsafe to start on ``host``, else None."""
    if is_loopback_host(host) or auth_required():
        return None
    if os.getenv("WEB2API_ALLOW_INSECURE", "").lower() in ("1", "true", "yes"):
        return None
    return (
        f"Refusing to listen on {host} without an API key: anyone on that network could use "
        f"your logged-in chat accounts.\n"
        f"  Fix: run 'python3 web2api_keys.py generate' (writes {keys_file_path()}),\n"
        f"       or set WEB2API_API_KEY, or bind to 127.0.0.1 and use an SSH tunnel."
    )


# OpenAI-compatible & FastAPI error formatting
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error": {
                "message": exc.detail,
                "type": "invalid_request_error" if exc.status_code < 500 else "api_error",
                "param": None,
                "code": exc.status_code,
            },
        },
    )


def sanitize_client_info(info: Optional[dict]) -> dict:
    """Drop/mask anything that could carry a key (e.g. the extension's endpoint URL with ?token=)."""
    clean = {}
    for k, v in (info or {}).items():
        if isinstance(v, str):
            v = TOKEN_IN_URL.sub(r"\1***", v)
            if KEY_IN_TEXT.search(v):
                v = KEY_IN_TEXT.sub("sk-w2a-***", v)
        clean[k] = v
    return clean


# Global Bridge Connection Hub
class ExtensionBridgeHub:
    def __init__(self):
        self.active_socket: Optional[WebSocket] = None
        self.pending_requests: dict[str, asyncio.Future] = {}
        self.lock = asyncio.Lock()
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "connected_since": None,
            "client_info": None,
        }

    @property
    def is_connected(self) -> bool:
        return self.active_socket is not None

    async def connect(self, websocket: WebSocket, client_info: Optional[dict] = None):
        self.active_socket = websocket
        self.stats["connected_since"] = datetime.now().isoformat()
        safe_info = sanitize_client_info(client_info)
        self.stats["client_info"] = safe_info
        print(f"[BRIDGE] Extension successfully connected via WebSocket: {safe_info}")

    def disconnect(self, websocket: Optional[WebSocket] = None):
        if websocket is not None and self.active_socket != websocket:
            return
        self.active_socket = None
        for req_id, future in self.pending_requests.items():
            if not future.done():
                future.set_exception(
                    HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Extension disconnected mid-request.",
                    )
                )
        self.pending_requests.clear()
        print("[BRIDGE] Extension disconnected.")

    async def dispatch_prompt(
        self, prompt: str, model: str = "gemini-pro", timeout: float = 120.0, mode: Optional[str] = None
    ) -> dict:
        if not self.is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Browser Extension is not connected. Please open your browser (Chrome/Firefox/Zen) and ensure the Web2API extension is active.",
            )

        req_id = f"req-{uuid.uuid4().hex[:12]}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        self.pending_requests[req_id] = future
        self.stats["total_requests"] += 1

        payload = {
            "id": req_id,
            "action": "CHAT",
            "prompt": prompt,
            "model": model,
            "mode": mode,
            "timeout": int(timeout * 1000),
        }

        try:
            async with self.lock:  # Process prompts sequentially to ensure browser focus stability
                await self.active_socket.send_text(json.dumps(payload))
                result = await asyncio.wait_for(future, timeout=timeout)
                self.stats["successful_requests"] += 1
                return result
        except asyncio.TimeoutError:
            self.stats["failed_requests"] += 1
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Request to browser chat session timed out after {timeout} seconds.",
            )
        except Exception:
            self.stats["failed_requests"] += 1
            raise
        finally:
            self.pending_requests.pop(req_id, None)

    async def reset_thread(self) -> dict:
        if not self.is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Browser Extension is not connected.",
            )
        req_id = f"req-{uuid.uuid4().hex[:12]}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending_requests[req_id] = future

        await self.active_socket.send_text(json.dumps({"id": req_id, "action": "RESET"}))
        try:
            return await asyncio.wait_for(future, timeout=10.0)
        finally:
            self.pending_requests.pop(req_id, None)

    def resolve_response(self, req_id: str, data: dict, error: Optional[str] = None):
        future = self.pending_requests.get(req_id)
        if not future or future.done():
            return

        if error:
            future.set_exception(
                HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error,
                )
            )
        else:
            future.set_result(data)


hub = ExtensionBridgeHub()


# WebSocket Endpoint for Browser Extension (Chrome / Firefox / Zen / Mock Harness)
@app.websocket("/ws")
@app.websocket("/ws/extension")
async def websocket_bridge(websocket: WebSocket):
    # Any web page can open a WebSocket to 127.0.0.1, so once keys exist the
    # extension must prove itself with ?token=<key> before it may receive prompts.
    token = websocket.query_params.get("token") or websocket.query_params.get("key")
    if auth_required() and not is_valid_key(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    client_info = {}
    try:
        # Wait for handshake
        handshake_raw = await websocket.receive_text()
        handshake = json.loads(handshake_raw)
        if handshake.get("type") in ("HANDSHAKE", "HELLO"):
            client_info = handshake
        await hub.connect(websocket, client_info)

        while True:
            message_raw = await websocket.receive_text()
            message = json.loads(message_raw)
            req_id = message.get("id") or message.get("jobId")
            req_status = message.get("status")

            if req_id:
                if req_status == "success" or "data" in message:
                    hub.resolve_response(req_id, message.get("data", {}))
                else:
                    hub.resolve_response(
                        req_id,
                        {},
                        error=message.get("error", "Unknown error from extension"),
                    )
    except WebSocketDisconnect:
        hub.disconnect(websocket)
    except Exception as e:
        print(f"[BRIDGE] WebSocket exception: {e}")
        hub.disconnect(websocket)


# Pydantic Schemas
class MessageItem(BaseModel):
    role: str = Field(..., description="Role of the author ('system', 'user', 'assistant', or 'tool')")
    content: Optional[str] = Field("", description="Message text content")
    name: Optional[str] = Field(None, description="Optional name for tool results or participants")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID for tool results")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls initiated by assistant")


class OpenAIChatRequest(BaseModel):
    model: str = Field("gemini-pro", description="Model name (e.g. gemini-pro, gpt-4o, claude-3-5-sonnet)")
    messages: list[MessageItem] = Field(..., description="List of messages comprising the conversation")
    temperature: Optional[float] = Field(0.7, description="Sampling temperature (emulated)")
    stream: Optional[bool] = Field(False, description="Whether to stream back partial chunks via Server-Sent Events")
    max_tokens: Optional[int] = Field(None, description="Maximum number of tokens to generate")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="List of tools available to the model")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field("auto", description="Controls tool selection ('auto', 'none', 'required', or specific tool)")


class Web2ApiRequest(BaseModel):
    prompt: str = Field(..., description="The direct prompt string to send to the browser AI")
    model: Optional[str] = Field("gemini-pro", description="Target model name")
    timeout: Optional[float] = Field(120.0, description="Max seconds to wait before timeout")


# REST Endpoints
class PairRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, description="6-digit code from 'web2api_keys.py pair'")


@app.post("/pair")
async def pair_extension(body: PairRequest, raw_request: Request):
    """
    Lets the browser extension on THIS device swap a one-time 6-digit code for its
    bridge URL, so nobody has to copy a long key on a phone keyboard.
    Loopback only: remote clients can never redeem codes.
    """
    client_host = raw_request.client.host if raw_request.client else ""
    if not is_loopback_host(client_host):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pairing is only allowed from this device.")
    result = redeem_pairing_code(body.code)
    if result != "ok":
        detail = {
            "invalid": "Wrong pairing code.",
            "expired": "Pairing code expired or used up. Create a new one: python3 web2api_keys.py pair",
            "none": "No pairing code active. Create one: python3 web2api_keys.py pair",
        }[result]
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    key = next(iter(load_keys()), None)
    if not key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Server has no API keys configured.")
    port = raw_request.url.port or PORT
    return {"bridge_url": f"ws://127.0.0.1:{port}/ws?token={key}"}


@app.get("/health")
@app.get("/status")
async def get_status(request: Request):
    """
    Server and extension connection status. Public callers get only the basics;
    client details and stats need a valid API key once keys are configured.
    """
    result = {
        "status": "online",
        "extension_connected": hub.is_connected,
        "auth_required": auth_required(),
        "timestamp": datetime.now().isoformat(),
    }
    auth_header = request.headers.get("authorization", "")
    provided = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else request.headers.get("x-api-key")
    if not auth_required() or is_valid_key(provided):
        result["active_client"] = hub.stats.get("client_info")
        result["stats"] = hub.stats
    return result


@app.get("/v1/models")
async def list_models():
    """Lists supported AI models."""
    return {
        "object": "list",
        "data": [
            # Gemini & Deep Research
            {"id": "gemini-deep-research", "object": "model", "owned_by": "google", "permission": []},
            {"id": "deep-research", "object": "model", "owned_by": "web2api", "permission": []},
            {"id": "gemini-pro", "object": "model", "owned_by": "google", "permission": []},
            {"id": "gemini-1.5-pro", "object": "model", "owned_by": "google", "permission": []},
            {"id": "gemini-1.5-flash", "object": "model", "owned_by": "google", "permission": []},
            {"id": "gemini-pro-web", "object": "model", "owned_by": "google", "permission": []},
            # ChatGPT
            {"id": "gpt-4o", "object": "model", "owned_by": "openai", "permission": []},
            {"id": "gpt-4o-mini", "object": "model", "owned_by": "openai", "permission": []},
            {"id": "chatgpt", "object": "model", "owned_by": "openai", "permission": []},
            # Claude
            {"id": "claude-3-5-sonnet", "object": "model", "owned_by": "anthropic", "permission": []},
            {"id": "claude-3-haiku", "object": "model", "owned_by": "anthropic", "permission": []},
            {"id": "claude", "object": "model", "owned_by": "anthropic", "permission": []},
        ],
    }


async def generate_sse_stream(
    chat_id: str,
    model_name: str,
    content: str,
    created_ts: int,
) -> AsyncGenerator[str, None]:
    """
    Yields standard Server-Sent Events (SSE) chunks for OpenAI-compatible streaming.
    Splits content into tokens with natural streaming pacing.
    """
    # 1. Role announcement chunk
    role_chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(role_chunk)}\n\n"

    # 2. Content delta chunks
    tokens = re.findall(r"\S+|\s+", content)
    for token in tokens:
        chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": token},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.005)

    # 3. Final stop chunk
    stop_chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(stop_chunk)}\n\n"
    yield "data: [DONE]\n\n"


async def generate_sse_tool_stream(
    chat_id: str,
    model_name: str,
    clean_content: Optional[str],
    tool_calls: List[Dict[str, Any]],
    created_ts: int,
) -> AsyncGenerator[str, None]:
    """
    Yields standard Server-Sent Events (SSE) chunks for OpenAI-compatible streaming tool calls.
    """
    # 1. Role announcement chunk
    role_chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(role_chunk)}\n\n"

    # 2. Content delta chunks (if thought or explanation exists)
    if clean_content:
        tokens = re.findall(r"\S+|\s+", clean_content)
        for token in tokens:
            content_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": token},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(content_chunk)}\n\n"
            await asyncio.sleep(0.002)

    # 3. Tool call delta chunks
    for tc_index, tc in enumerate(tool_calls):
        tc_id = tc["id"]
        fn_name = tc["function"]["name"]
        fn_args = tc["function"]["arguments"]

        # Initial tool call descriptor
        init_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": tc_index,
                                "id": tc_id,
                                "type": "function",
                                "function": {
                                    "name": fn_name,
                                    "arguments": "",
                                },
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(init_chunk)}\n\n"

        # Stream argument tokens
        arg_tokens = re.findall(r"\S+|\s+", fn_args)
        for tok in arg_tokens:
            arg_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": tc_index,
                                    "function": {"arguments": tok},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(arg_chunk)}\n\n"
            await asyncio.sleep(0.002)

    # 4. Final stop chunk with finish_reason: "tool_calls"
    stop_chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "tool_calls",
            }
        ],
    }
    yield f"data: {json.dumps(stop_chunk)}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def openai_chat_completions(req: OpenAIChatRequest, raw_request: Request):
    """
    Standard OpenAI-compatible Chat Completions API with full Tool Calling emulation.
    Supports both non-streaming JSON and streaming Server-Sent Events (SSE).
    Works seamlessly with LangChain, LlamaIndex, Cursor, Continue, AutoGen, and curl!
    """
    await verify_api_key(raw_request)

    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages array cannot be empty.")

    # Format prompt, handling tool schemas and tool result messages
    if req.tools:
        prompt_text = format_conversation_with_tools(req.messages, req.tools, req.tool_choice)
    elif len(req.messages) == 1:
        prompt_text = req.messages[0].content or ""
    else:
        formatted = []
        for m in req.messages:
            role = m.role.capitalize()
            content_val = m.content or ""
            formatted.append(f"[{role}]: {content_val}")
        prompt_text = "\n\n".join(formatted) + "\n\n[Assistant]:"

    # Deep Research directive injection for Gemini & deep-research models
    is_deep_research = "deep-research" in req.model.lower() or req.model.lower() == "gemini-deep-research"
    if is_deep_research:
        deep_directive = (
            "[SYSTEM DIRECTIVE: DEEP RESEARCH & EXHAUSTIVE CITATION MODE]\n"
            "Conduct exhaustive, multi-perspective in-depth research on the following user query.\n"
            "Structure your output as an authoritative, publication-ready research dossier:\n"
            "- Executive Summary & Core Thesis\n"
            "- Deep Technical & Architectural Analysis\n"
            "- Empirical Evidence, Real-world Citations & Nuances\n"
            "- Multi-angle Trade-offs & Counter-Arguments\n"
            "- Strategic Findings & Actionable Recommendations\n\n"
        )
        prompt_text = deep_directive + prompt_text

    start_time = time.time()
    mode = "deep-research" if is_deep_research else None
    response_data = await hub.dispatch_prompt(prompt_text, model=req.model, mode=mode)
    elapsed = time.time() - start_time
    created_ts = int(time.time())
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    content_text = ""
    if "choices" in response_data and len(response_data["choices"]) > 0:
        content_text = response_data["choices"][0].get("message", {}).get("content", "")
    elif "text" in response_data:
        content_text = response_data["text"]
    else:
        content_text = str(response_data)

    # Tool calling detection and parsing
    tool_calls = []
    clean_content = content_text
    if req.tools and req.tool_choice != "none":
        clean_content, tool_calls = parse_tool_calls(content_text, req.tools)

    # 1. Streaming Response (Server-Sent Events)
    if req.stream:
        if tool_calls:
            stream_gen = generate_sse_tool_stream(chat_id, req.model, clean_content, tool_calls, created_ts)
        else:
            stream_gen = generate_sse_stream(chat_id, req.model, content_text, created_ts)

        return StreamingResponse(
            stream_gen,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 2. Non-Streaming Response with Tool Calls
    if tool_calls:
        return {
            "id": chat_id,
            "object": "chat.completion",
            "created": created_ts,
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": clean_content,
                        "tool_calls": tool_calls,
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt_text) // 4,
                "completion_tokens": len(content_text) // 4,
                "total_tokens": (len(prompt_text) + len(content_text)) // 4,
            },
            "extracted": response_data.get("extracted", {}),
            "latency_seconds": round(elapsed, 2),
        }

    # 3. Non-Streaming JSON Response (Already fully formatted)
    if "choices" in response_data and "usage" in response_data:
        response_data["latency_seconds"] = round(elapsed, 2)
        return response_data

    # 4. Standard Non-Streaming JSON Response
    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(prompt_text) // 4,
            "completion_tokens": len(content_text) // 4,
            "total_tokens": (len(prompt_text) + len(content_text)) // 4,
        },
        "extracted": response_data.get("extracted", {}),
        "latency_seconds": round(elapsed, 2),
    }


@app.post("/api/chat")
async def web2api_chat(req: Web2ApiRequest, raw_request: Request):
    """
    Simplified direct prompt endpoint.
    """
    await verify_api_key(raw_request)

    start_time = time.time()
    response_data = await hub.dispatch_prompt(
        req.prompt, model=req.model or "gemini-pro", timeout=req.timeout or 120.0
    )
    elapsed = time.time() - start_time

    content = ""
    if "choices" in response_data and len(response_data["choices"]) > 0:
        content = response_data["choices"][0].get("message", {}).get("content", "")
    elif "text" in response_data:
        content = response_data["text"]
    else:
        content = str(response_data)

    return {
        "response": content,
        "extracted": response_data.get("extracted", {}),
        "latency_seconds": round(elapsed, 2),
        "status": "success",
    }


@app.post("/api/reset")
async def reset_conversation(raw_request: Request):
    """
    Resets the conversation thread in the active browser tab.
    """
    await verify_api_key(raw_request)
    res = await hub.reset_thread()
    return {"status": "success", "message": "Conversation thread reset", "details": res}


def parse_hosts(raw: str) -> List[str]:
    """Split a comma-separated HOST value into addresses (defaults to loopback)."""
    return [h.strip() for h in raw.split(",") if h.strip()] or ["127.0.0.1"]


def bind_sockets(hosts: List[str], port: int) -> List[socket.socket]:
    """Pre-bind one listening socket per address so uvicorn can serve them all."""
    sockets = []
    for host in hosts:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.set_inheritable(True)
        sockets.append(sock)
    return sockets


if __name__ == "__main__":
    hosts = parse_hosts(HOST)
    for bind_host in hosts:
        problem = check_startup_security(bind_host)
        if problem:
            print(f"[ERROR] {problem}", file=sys.stderr)
            sys.exit(1)
    for bind_host in hosts:
        print(f"[INFO] Launching Web2API Universal Bridge Server on http://{bind_host}:{PORT}")
    print(f"[INFO] WebSocket endpoints: /ws, /ws/extension on port {PORT}")
    if auth_required():
        print(f"[INFO] Security: API key authentication ENABLED ({len(get_allowed_api_keys())} key(s)).")
        print("[INFO] Extension bridge URL must include ?token=<key>  (see api.txt)")
    else:
        print("[INFO] Security: no API key configured - loopback-only open access.")
    if len(hosts) == 1:
        uvicorn.run("bridge_server:app", host=hosts[0], port=PORT, reload=False)
    else:
        server = uvicorn.Server(uvicorn.Config(app, port=PORT, reload=False))
        server.run(sockets=bind_sockets(hosts, PORT))
