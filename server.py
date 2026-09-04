# server.py - FastAPI web server for the Gemini Web2API project.
# This module exposes the HTTP API that wraps the automated Gemini browser session.
# It handles routing, request/response validation, diagnostic logging, and startup/shutdown of the browser.

import os
import sys
import time
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, List, Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from session_manager import GeminiSessionManager, SessionUnauthenticatedException

# Resolve pathing
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
SESSION_DIR = os.path.join(BASE_DIR, ".playwright_session")

# Server Config (overridable via env vars; see docs/configuration.md)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")

# Initialize session manager (the browser automation engine)
manager = GeminiSessionManager(session_dir=SESSION_DIR, headless=HEADLESS)

# Global variables for diagnostics
request_logs: List[Dict[str, Any]] = []
log_id_counter = 1
total_requests = 0
total_success = 0
total_latency = 0.0

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Try to start browser session
    print("[INFO] Starting browser session manager on startup...")
    # Check if session folder exists (meaning they ran auth setup)
    if not os.path.exists(SESSION_DIR):
        print("[WARNING] Playwright session folder does not exist yet.")
        print("[WARNING] Please run './start.sh auth' to log in manually first.")
        manager.status = "Awaiting Authentication"
    else:
        # Start browser manager asynchronously (don't block server startup)
        asyncio.create_task(start_browser_background())
    yield
    # Shutdown: Safely stop browser session
    print("[INFO] Stopping browser session manager on shutdown...")
    await manager.stop()

async def start_browser_background():
    # Helper: start the browser without blocking; logs failures on error
    try:
        await manager.start()
    except Exception as e:
        print(f"[ERROR] Failed to start browser in background: {e}")

app = FastAPI(
    title="Gemini Web2API Server",
    description="A local API wrapper around the Gemini Web Chat Interface",
    version="1.0.0",
    lifespan=lifespan
)

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Pydantic schemas - define the shape of API request/response bodies
class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="The prompt query to send to Gemini")
    timeout_sec: int = Field(90, ge=10, le=180, description="Max seconds to wait for generation")

class ChatResponse(BaseModel):
    response: str
    latency_ms: float
    status: str

# Helper to add a diagnostics log entry (newest first, capped at 50)
def add_log(prompt: str, response: str, latency_ms: float, status_str: str):
    global log_id_counter, total_requests, total_success, total_latency
    
    total_requests += 1
    # Only successful calls count toward latency averages
    if status_str == "Success":
        total_success += 1
        total_latency += latency_ms
        
    # Build a concise log entry with truncated prompt/response snippets
    log_entry = {
        "id": log_id_counter,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prompt": prompt[:80] + "..." if len(prompt) > 80 else prompt,
        "response": response[:120] + "..." if len(response) > 120 else response,
        "latency_ms": round(latency_ms, 2),
        "status": status_str
    }
    request_logs.insert(0, log_entry)
    log_id_counter += 1
    
    # Keep log history capped at 50 elements
    if len(request_logs) > 50:
        request_logs.pop()

# Server Dashboard HTML route
@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    # Render the Jinja2 admin dashboard template
    return templates.TemplateResponse("index.html", {"request": request})

# Active Chat API Endpoint
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    # Reject the request if the browser session isn't ready
    if not manager.is_connected:
        # Check if browser is just booting or if it's failed
        if manager.status == "Awaiting Authentication":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Server is not authenticated. Please run './start.sh auth' to log in manually."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Browser is not connected. Current status: {manager.status}. Error: {manager.last_error}"
            )
            
    start_time = time.time()
    try:
        # Delegate to the browser automation engine
        response_text = await manager.send_prompt(
            prompt_text=payload.prompt,
            timeout_sec=payload.timeout_sec
        )
        elapsed_ms = (time.time() - start_time) * 1000
        add_log(payload.prompt, response_text, elapsed_ms, "Success")
        
        return ChatResponse(
            response=response_text,
            latency_ms=elapsed_ms,
            status="Success"
        )
    except SessionUnauthenticatedException as e:
        # Session was lost during the request (e.g. redirected to login)
        elapsed_ms = (time.time() - start_time) * 1000
        add_log(payload.prompt, str(e), elapsed_ms, "Authentication Error")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        # Any other failure: timeout, browser error, DOM mismatch, etc.
        elapsed_ms = (time.time() - start_time) * 1000
        add_log(payload.prompt, str(e), elapsed_ms, "System Error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat prompt: {str(e)}"
        )

# Get Session Status
@app.get("/api/status")
async def get_status():
    # Report system health, session state, and usage stats for the dashboard
    session_exists = os.path.exists(SESSION_DIR)
    avg_latency = 0.0
    if total_success > 0:
        avg_latency = round(total_latency / total_success, 2)
        
    return {
        "status": manager.status,
        "is_connected": manager.is_connected,
        "session_exists": session_exists,
        "headless": manager.headless,
        "last_error": manager.last_error,
        "last_activity": manager.last_activity.strftime("%Y-%m-%d %H:%M:%S") if manager.last_activity else "None",
        "total_requests": total_requests,
        "total_success": total_success,
        "avg_latency_ms": avg_latency
    }

# Get Current browser Screenshot
@app.get("/api/screenshot")
async def get_screenshot():
    # Capture the live browser page as a base64 PNG for the "Live Headless View"
    screenshot_b64 = await manager.take_screenshot_base64()
    return {"screenshot": screenshot_b64}

# Get diagnostic request logs
@app.get("/api/logs")
async def get_logs():
    # Return the in-memory request log list for the dashboard table
    return request_logs

# Quick recovery reboot endpoint
@app.post("/api/reconnect")
async def reconnect_browser():
    # Stop and restart the browser session without blocking the response
    try:
        await manager.stop()
        # Start recovery task in background to avoid blocking request
        asyncio.create_task(start_browser_background())
        return {"status": "Reconnect command initiated."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger reconnect: {e}"
        )

# Reset Conversation Thread Endpoint
@app.post("/api/chat/reset")
async def reset_chat():
    # Start a fresh conversation in the persistent Gemini thread
    if not manager.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Browser session is not connected."
        )
    try:
        await manager.new_chat()
        return {"status": "New conversation thread initialized successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset conversation thread: {e}"
        )

# Streaming Chat Endpoint (Server-Sent Events / Chunked)
@app.post("/api/chat/stream")
async def chat_stream_endpoint(payload: ChatRequest):
    # Same as /api/chat but yields response deltas as SSE events for real-time streaming
    if not manager.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Browser session is not connected."
        )

    async def event_generator():
        start_time = time.time()
        full_text = ""
        try:
            # Yield each text delta as an SSE "data:" event
            async for chunk in manager.send_prompt_stream(payload.prompt, payload.timeout_sec):
                full_text += chunk
                yield f"data: {chunk}\n\n"
            elapsed_ms = (time.time() - start_time) * 1000
            add_log(payload.prompt, full_text, elapsed_ms, "Success")
            yield "data: [DONE]\n\n"
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            add_log(payload.prompt, str(e), elapsed_ms, "System Error")
            yield f"data: [ERROR: {str(e)}]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    print(f"Starting Web2API Server on http://{HOST}:{PORT}...")
    uvicorn.run("server:app", host=HOST, port=PORT, reload=False)
