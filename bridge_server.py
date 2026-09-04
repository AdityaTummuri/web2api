"""
bridge_server.py - Web2API Firefox Extension Bridge Server
Exposes an OpenAI-compatible REST API (and Web2API endpoints) that routes
requests directly into your authenticated Firefox browser session via WebSocket.
"""

import os
import sys
import time
import json
import uuid
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(
    title="Web2API Firefox Bridge Server",
    description="Transforms your live Firefox browser chat session into a high-speed OpenAI-compatible API.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Bridge Connection Hub
class ExtensionBridgeHub:
    def __init__(self):
        self.active_socket: Optional[WebSocket] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.lock = asyncio.Lock()
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "connected_since": None,
            "client_info": None
        }

    @property
    def is_connected(self) -> bool:
        return self.active_socket is not None

    async def connect(self, websocket: WebSocket, client_info: dict = None):
        self.active_socket = websocket
        self.stats["connected_since"] = datetime.now().isoformat()
        self.stats["client_info"] = client_info or {}
        print("[BRIDGE] Firefox Extension successfully connected via WebSocket.")

    def disconnect(self):
        self.active_socket = None
        self.stats["client_info"] = None
        # Cancel any pending futures
        for req_id, future in self.pending_requests.items():
            if not future.done():
                future.set_exception(HTTPException(status_code=503, detail="Firefox extension disconnected mid-request."))
        self.pending_requests.clear()
        print("[BRIDGE] Firefox Extension disconnected.")

    async def dispatch_prompt(self, prompt: str, model: str = "gemini-pro", timeout: float = 120.0) -> dict:
        if not self.is_connected:
            raise HTTPException(
                status_code=503,
                detail="Firefox Extension is not connected. Please open Firefox and ensure the Web2API Pro extension is active."
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
            "timeout": int(timeout * 1000)
        }

        try:
            async with self.lock:  # Process prompts sequentially to ensure browser focus stability
                await self.active_socket.send_text(json.dumps(payload))
                result = await asyncio.wait_for(future, timeout=timeout)
                self.stats["successful_requests"] += 1
                return result
        except asyncio.TimeoutError:
            self.stats["failed_requests"] += 1
            raise HTTPException(status_code=504, detail=f"Request to Firefox chat session timed out after {timeout} seconds.")
        except Exception as e:
            self.stats["failed_requests"] += 1
            raise
        finally:
            self.pending_requests.pop(req_id, None)

    async def reset_thread(self) -> dict:
        if not self.is_connected:
            raise HTTPException(status_code=503, detail="Firefox Extension is not connected.")
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
            future.set_exception(HTTPException(status_code=500, detail=error))
        else:
            future.set_result(data)

hub = ExtensionBridgeHub()

# WebSocket Endpoint for Firefox Extension
@app.websocket("/ws")
async def websocket_bridge(websocket: WebSocket):
    await websocket.accept()
    client_info = {}
    try:
        # Wait for handshake
        handshake_raw = await websocket.receive_text()
        handshake = json.loads(handshake_raw)
        if handshake.get("type") == "HANDSHAKE":
            client_info = handshake
        await hub.connect(websocket, client_info)

        while True:
            message_raw = await websocket.receive_text()
            message = json.loads(message_raw)
            req_id = message.get("id")
            status = message.get("status")

            if req_id:
                if status == "success":
                    hub.resolve_response(req_id, message.get("data", {}))
                else:
                    hub.resolve_response(req_id, {}, error=message.get("error", "Unknown error from extension"))
    except WebSocketDisconnect:
        hub.disconnect()
    except Exception as e:
        print(f"[BRIDGE] WebSocket exception: {e}")
        hub.disconnect()

# Pydantic Schemas
class MessageItem(BaseModel):
    role: str
    content: str

class OpenAIChatRequest(BaseModel):
    model: str = "gemini-pro"
    messages: List[MessageItem]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None

class Web2ApiRequest(BaseModel):
    prompt: str
    model: Optional[str] = "gemini-pro"
    timeout: Optional[float] = 120.0

# REST Endpoints
@app.get("/health")
@app.get("/status")
async def get_status():
    return {
        "status": "online",
        "extension_connected": hub.is_connected,
        "active_client": hub.stats.get("client_info"),
        "stats": hub.stats,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "gemini-pro", "object": "model", "owned_by": "web2api", "permission": []},
            {"id": "gemini-1.5-pro", "object": "model", "owned_by": "web2api", "permission": []},
            {"id": "gemini-1.5-flash", "object": "model", "owned_by": "web2api", "permission": []},
            {"id": "gemini-pro-web", "object": "model", "owned_by": "web2api", "permission": []}
        ]
    }

@app.post("/v1/chat/completions")
async def openai_chat_completions(req: OpenAIChatRequest):
    """
    Standard OpenAI-compatible Chat Completions API.
    Works seamlessly with LangChain, LlamaIndex, Cursor, AutoGen, and curl!
    """
    # Synthesize messages into prompt
    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages array cannot be empty.")

    # If multiple messages, format with role prefixes
    if len(req.messages) == 1:
        prompt_text = req.messages[0].content
    else:
        formatted = []
        for m in req.messages:
            role = m.role.capitalize()
            formatted.append(f"[{role}]: {m.content}")
        prompt_text = "\n\n".join(formatted) + "\n\n[Assistant]:"

    start_time = time.time()
    response_data = await hub.dispatch_prompt(prompt_text, model=req.model)
    elapsed = time.time() - start_time

    # Ensure valid OpenAI response format
    if "choices" in response_data:
        return response_data

    # Fallback structure
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_data.get("text", "")
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": len(prompt_text) // 4,
            "completion_tokens": len(response_data.get("text", "")) // 4,
            "total_tokens": (len(prompt_text) + len(response_data.get("text", ""))) // 4
        },
        "latency_seconds": round(elapsed, 2)
    }

@app.post("/api/chat")
async def web2api_chat(req: Web2ApiRequest):
    """
    Simplified direct prompt endpoint.
    """
    start_time = time.time()
    response_data = await hub.dispatch_prompt(req.prompt, model=req.model or "gemini-pro", timeout=req.timeout or 120.0)
    elapsed = time.time() - start_time

    content = ""
    if "choices" in response_data and len(response_data["choices"]) > 0:
        content = response_data["choices"][0]["message"]["content"]
    else:
        content = str(response_data)

    return {
        "response": content,
        "extracted": response_data.get("extracted", {}),
        "latency_seconds": round(elapsed, 2),
        "status": "success"
    }

@app.post("/api/reset")
async def reset_conversation():
    """
    Resets the conversation thread in the Gemini browser tab.
    """
    res = await hub.reset_thread()
    return {"status": "success", "message": "Conversation thread reset", "details": res}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    print(f"[INFO] Launching Web2API Firefox Bridge on http://{host}:{port}")
    print(f"[INFO] WebSocket endpoint for Firefox extension: ws://{host}:{port}/ws")
    uvicorn.run("bridge_server:app", host=host, port=port, reload=False)
