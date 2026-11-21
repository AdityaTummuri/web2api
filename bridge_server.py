"""
bridge_server.py - Web2API Universal Bridge Server
Exposes an OpenAI-compatible REST API (and Web2API endpoints) that routes
requests directly into an authenticated browser session (Chrome, Firefox, Zen, etc.) via WebSocket.
Can be run locally or deployed independently on any remote server / container.
"""

import asyncio
import json
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Security, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from tool_parser import format_conversation_with_tools, parse_tool_calls

# Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
API_KEY = os.getenv("WEB2API_API_KEY") or os.getenv("API_KEY")
CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [orig.strip() for orig in CORS_ORIGINS_RAW.split(",") if orig.strip()] or ["*"]

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

security_bearer = HTTPBearer(auto_error=False)


async def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
):
    """
    Optional API Key protection. If WEB2API_API_KEY / API_KEY is set in environment,
    require valid Bearer token or 'X-API-Key' header.
    """
    if not API_KEY:
        return True

    # 1. Check Bearer token
    if credentials and credentials.credentials == API_KEY:
        return True

    # 2. Check X-API-Key header
    header_key = request.headers.get("x-api-key")
    if header_key and header_key == API_KEY:
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Invalid or missing API key. Provide 'Authorization: Bearer <KEY>' or 'X-API-Key: <KEY>'.",
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
        self.stats["client_info"] = client_info or {}
        print(f"[BRIDGE] Extension successfully connected via WebSocket: {client_info}")

    def disconnect(self):
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
        self, prompt: str, model: str = "gemini-pro", timeout: float = 120.0
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
    # If API_KEY is set, check optional token in query param
    token = websocket.query_params.get("token") or websocket.query_params.get("key")
    if API_KEY and token != API_KEY:
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
        hub.disconnect()
    except Exception as e:
        print(f"[BRIDGE] WebSocket exception: {e}")
        hub.disconnect()


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
@app.get("/health")
@app.get("/status")
async def get_status():
    """Returns server and extension connection status."""
    return {
        "status": "online",
        "extension_connected": hub.is_connected,
        "active_client": hub.stats.get("client_info"),
        "stats": hub.stats,
        "auth_required": bool(API_KEY),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/v1/models")
async def list_models():
    """Lists supported AI models."""
    return {
        "object": "list",
        "data": [
            # Gemini
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

    start_time = time.time()
    response_data = await hub.dispatch_prompt(prompt_text, model=req.model)
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


if __name__ == "__main__":
    print(f"[INFO] Launching Web2API Universal Bridge Server on http://{HOST}:{PORT}")
    print(f"[INFO] WebSocket endpoints: ws://{HOST}:{PORT}/ws, ws://{HOST}:{PORT}/ws/extension")
    if API_KEY:
        print("[INFO] Security: API Key authentication ENABLED.")
    else:
        print("[INFO] Security: Open access (no API key set).")
    uvicorn.run("bridge_server:app", host=HOST, port=PORT, reload=False)
