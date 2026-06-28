import os
import sys
import time
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, List, Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from session_manager import GeminiSessionManager, SessionUnauthenticatedException

# Resolve pathing
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
SESSION_DIR = os.path.join(BASE_DIR, ".playwright_session")

# Server Config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")

# Initialize session manager
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
        # Start browser manager asynchronously
        asyncio.create_task(start_browser_background())
    yield
    # Shutdown: Safely stop browser session
    print("[INFO] Stopping browser session manager on shutdown...")
    await manager.stop()

async def start_browser_background():
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

# Pydantic schemas
class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="The prompt query to send to Gemini")
    timeout_sec: int = Field(90, ge=10, le=180, description="Max seconds to wait for generation")

class ChatResponse(BaseModel):
    response: str
    latency_ms: float
    status: str

# Helper to add diagnostics logs
def add_log(prompt: str, response: str, latency_ms: float, status_str: str):
    global log_id_counter, total_requests, total_success, total_latency
    
    total_requests += 1
    if status_str == "Success":
        total_success += 1
        total_latency += latency_ms
        
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
    return templates.TemplateResponse("index.html", {"request": request})

# Active Chat API Endpoint
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
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
        elapsed_ms = (time.time() - start_time) * 1000
        add_log(payload.prompt, str(e), elapsed_ms, "Authentication Error")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        add_log(payload.prompt, str(e), elapsed_ms, "System Error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat prompt: {str(e)}"
        )

# Get Session Status
@app.get("/api/status")
async def get_status():
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
    screenshot_b64 = await manager.take_screenshot_base64()
    return {"screenshot": screenshot_b64}

# Get diagnostic request logs
@app.get("/api/logs")
async def get_logs():
    return request_logs

# Quick recovery reboot endpoint
@app.post("/api/reconnect")
async def reconnect_browser():
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

if __name__ == "__main__":
    import uvicorn
    print(f"Starting Web2API Server on http://{HOST}:{PORT}...")
    uvicorn.run("server:app", host=HOST, port=PORT, reload=False)
