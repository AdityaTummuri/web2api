# session_manager.py - Core browser automation engine for the Gemini Web2API project.
# This module encapsulates all interaction with gemini.google.com using Playwright:
# launching the browser, navigating, submitting prompts, reading streamed responses,
# self-healing on crashes, and resetting the conversation thread.

import asyncio
import os
import base64
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

class SessionUnauthenticatedException(Exception):
    """Raised when the session is not logged into Google/Gemini."""
    pass

class GeminiSessionManager:
    def __init__(self, session_dir: str, headless: bool = True):
        self.session_dir = session_dir  # Persistent Chromium profile (cookies/localStorage)
        self.headless = headless
        self.playwright = None
        self.context = None
        self.page = None
        self.lock = asyncio.Lock()  # Serializes all browser interactions (one request at a time)
        self.status = "Disconnected"
        self.is_connected = False
        self.last_error = None
        self.last_activity = None
        
        # CSS selectors that match Gemini's web UI DOM
        self.INPUT_SELECTOR = 'div[contenteditable="true"]'
        self.SEND_BUTTON_SELECTOR = 'button[aria-label*="Send" i], button[aria-label*="send" i], button:has-text("Send"), button.send-button'
        self.STOP_BUTTON_SELECTOR = 'button[aria-label*="Stop" i], button[aria-label*="stop" i]'
        self.MESSAGE_SELECTORS = ['message-content', '[class*="message-content"]', '.message-content', 'article']
        self.NEW_CHAT_SELECTOR = 'a[href*="/app"], button[aria-label*="New chat" i], button[aria-label*="Reset" i], [data-test-id="new-chat-button"]'

    async def start(self):
        """Launches the persistent Playwright browser context."""
        try:
            self.status = "Starting browser..."
            self.playwright = await async_playwright().start()
            
            # Launch Chromium using the authenticated user data directory
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.session_dir,
                headless=self.headless,
                viewport={"width": 1280, "height": 850},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )
            
            # Use an existing page or create a new one
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
                
            # Apply stealth patches to reduce bot-detection risk
            await stealth_async(self.page)
            
            # Navigate directly to the chat app
            self.status = "Navigating to Gemini..."
            await self.page.goto("https://gemini.google.com/app", timeout=30000)
            
            # Verify if logged in by looking for the chat input
            await self.verify_authentication()
            
            self.is_connected = True
            self.status = "Connected & Ready"
            self.last_activity = datetime.now()
            print("[INFO] Playwright browser session started and verified successfully.")
            
        except SessionUnauthenticatedException as e:
            # Not logged in - report and let the server surface this to the user
            self.is_connected = False
            self.status = "Awaiting Authentication"
            self.last_error = str(e)
            print(f"[ERROR] Session verification failed: {e}")
            raise
        except Exception as e:
            # Any other startup failure - clean up and re-raise
            self.is_connected = False
            self.status = "Failed to Start"
            self.last_error = str(e)
            print(f"[ERROR] Failed to start session manager: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Safely shuts down the browser context."""
        self.status = "Stopping..."
        self.is_connected = False
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.page = None
        self.context = None
        self.playwright = None
        self.status = "Disconnected"

    async def verify_authentication(self):
        """Verifies if the session is currently authenticated on the Gemini page."""
        try:
            # Wait up to 10s for the contenteditable textbox to appear
            await self.page.wait_for_selector(self.INPUT_SELECTOR, timeout=10000)
        except Exception:
            url = self.page.url
            if "signin" in url or "accounts.google.com" in url:
                raise SessionUnauthenticatedException(
                    "Redirected to Google Login. Please run './start.sh auth' first to authenticate."
                )
            else:
                raise SessionUnauthenticatedException(
                    "Prompt input box not found. Make sure you are logged in and session is initialized."
                )

    async def check_and_recover(self):
        """Checks browser connection health and attempts a restart if closed/crashed."""
        is_healthy = False
        if self.page and not self.page.is_closed():
            try:
                # A trivial JS evaluation proves the page is alive
                await self.page.evaluate("1 + 1")
                is_healthy = True
            except Exception:
                pass
                
        if not is_healthy:
            # Browser crashed or tab closed - restart the whole session
            print("[WARNING] Browser connection lost. Attempting recovery...")
            await self.stop()
            await self.start()

    async def get_response_locator(self, index: int):
        """Returns the locator of the message response at the given index."""
        for selector in self.MESSAGE_SELECTORS:
            locator = self.page.locator(selector)
            if await locator.count() > index:
                return locator.nth(index)
        return None

    async def send_prompt(self, prompt_text: str, timeout_sec: int = 90) -> str:
        """Sends a prompt, waits for generation to stabilize, and returns the response."""
        async with self.lock:
            self.last_activity = datetime.now()
            await self.check_and_recover()
            
            # Final check that we are authenticated and on the right page
            await self.verify_authentication()
            
            # Count the existing responses to know where the new one will appear
            initial_count = 0
            for selector in self.MESSAGE_SELECTORS:
                cnt = await self.page.locator(selector).count()
                if cnt > initial_count:
                    initial_count = cnt
            
            print(f"[INFO] Initial message-content count: {initial_count}")
            
            self.status = "Sending prompt..."
            input_box = self.page.locator(self.INPUT_SELECTOR).first
            await input_box.focus()
            
            # Fill the prompt text
            await input_box.fill(prompt_text)
            # Brief pause so the UI registers the input before we click send
            await asyncio.sleep(0.2)
            
            # Look for send button and click it
            sent = False
            send_btn = self.page.locator(self.SEND_BUTTON_SELECTOR).first
            if await send_btn.is_visible() and await send_btn.is_enabled():
                try:
                    await send_btn.click()
                    sent = True
                    print("[INFO] Clicked the send button.")
                except Exception:
                    pass
            
            if not sent:
                # Fallback: Press Enter inside the prompt input
                await input_box.press("Enter")
                print("[INFO] Pressed Enter inside prompt box.")
                
            self.status = "Generating response..."
            
            # 1. Wait for the new response element to be appended (timeout: 10s)
            start_time = datetime.now()
            target_locator = None
            
            for _ in range(20): # 10 seconds max wait for element creation (20 * 0.5s)
                for selector in self.MESSAGE_SELECTORS:
                    cnt = await self.page.locator(selector).count()
                    if cnt > initial_count:
                        # Grab the newly created response element (nth index = initial_count)
                        target_locator = self.page.locator(selector).nth(initial_count)
                        break
                if target_locator:
                    break
                await asyncio.sleep(0.5)
                
            if not target_locator:
                self.status = "Error: Timeout"
                raise TimeoutError("Timeout waiting for Gemini to start responding.")
                
            # 2. Wait for text generation to stabilize (no text changes for 1.5s)
            last_text = ""
            stable_count = 0
            check_interval = 0.5 # check every 500ms
            max_checks = int(timeout_sec / check_interval)
            
            print("[INFO] Streaming response detected. Waiting for text stabilization...")
            
            for i in range(max_checks):
                # Retrieve current text
                current_text = await target_locator.inner_text()
                current_text = current_text.strip()
                
                # Check if stop button is visible (meaning it's still printing)
                stop_btn = self.page.locator(self.STOP_BUTTON_SELECTOR).first
                stop_visible = await stop_btn.is_visible() if stop_btn else False
                
                # Compare with previous snapshot
                if len(current_text) > 0 and current_text == last_text:
                    stable_count += 1
                else:
                    stable_count = 0
                    
                last_text = current_text
                
                # We consider it finished if:
                # - Text is not empty AND didn't change for 1.5s (3 stable intervals of 500ms) AND stop button is gone
                if len(current_text) > 0 and stable_count >= 3 and not stop_visible:
                    print(f"[INFO] Response stabilized in {(i * check_interval):.1f}s.")
                    break
                    
                await asyncio.sleep(check_interval)
            else:
                print("[WARNING] Response did not stabilize within timeout. Returning partial response.")
                
            self.status = "Connected & Ready"
            return last_text

    async def new_chat(self) -> bool:
        """Resets the conversation context by navigating to a fresh chat thread."""
        async with self.lock:
            self.last_activity = datetime.now()
            await self.check_and_recover()
            
            try:
                self.status = "Resetting conversation..."
                # Try clicking new chat button if available, otherwise navigate to /app
                new_btn = self.page.locator(self.NEW_CHAT_SELECTOR).first
                if await new_btn.is_visible():
                    await new_btn.click()
                    await asyncio.sleep(1.0)
                else:
                    await self.page.goto("https://gemini.google.com/app", timeout=30000)
                
                await self.verify_authentication()
                self.status = "Connected & Ready"
                print("[INFO] Started new chat thread successfully.")
                return True
            except Exception as e:
                print(f"[ERROR] Failed to reset chat thread: {e}")
                self.status = "Connected & Ready"
                raise e

    async def send_prompt_stream(self, prompt_text: str, timeout_sec: int = 90):
        """Yields streaming response text tokens asynchronously as they stabilize.

        Unlike send_prompt(), this does not wait for full stabilization - it
        yields each newly-observed chunk of text so the server can forward it
        as Server-Sent Events in real time.
        """
        async with self.lock:
            self.last_activity = datetime.now()
            await self.check_and_recover()
            await self.verify_authentication()
            
            initial_count = 0
            for selector in self.MESSAGE_SELECTORS:
                cnt = await self.page.locator(selector).count()
                if cnt > initial_count:
                    initial_count = cnt
                    
            self.status = "Sending prompt..."
            input_box = self.page.locator(self.INPUT_SELECTOR).first
            await input_box.focus()
            await input_box.fill(prompt_text)
            await asyncio.sleep(0.2)
            
            # Click send button, falling back to Enter key
            sent = False
            send_btn = self.page.locator(self.SEND_BUTTON_SELECTOR).first
            if await send_btn.is_visible() and await send_btn.is_enabled():
                try:
                    await send_btn.click()
                    sent = True
                except Exception:
                    pass
            if not sent:
                await input_box.press("Enter")
                
            self.status = "Generating response..."
            
            # Wait for the new response element to appear (up to 10s)
            target_locator = None
            for _ in range(20):
                for selector in self.MESSAGE_SELECTORS:
                    cnt = await self.page.locator(selector).count()
                    if cnt > initial_count:
                        target_locator = self.page.locator(selector).nth(initial_count)
                        break
                if target_locator:
                    break
                await asyncio.sleep(0.5)
                
            if not target_locator:
                self.status = "Error: Timeout"
                raise TimeoutError("Timeout waiting for Gemini to start responding.")
                
            last_text = ""
            stable_count = 0
            check_interval = 0.4  # poll every 400ms for streaming
            max_checks = int(timeout_sec / check_interval)
            
            for i in range(max_checks):
                current_text = await target_locator.inner_text()
                current_text = current_text.strip()
                
                stop_btn = self.page.locator(self.STOP_BUTTON_SELECTOR).first
                stop_visible = await stop_btn.is_visible() if stop_btn else False
                
                # If text grew, yield the newly appended portion (delta)
                if len(current_text) > len(last_text):
                    delta = current_text[len(last_text):]
                    yield delta
                    stable_count = 0
                elif len(current_text) > 0 and current_text == last_text:
                    stable_count += 1
                else:
                    stable_count = 0
                    
                last_text = current_text
                
                # Stop when stable for 1.2s (3 * 400ms) AND stop button gone
                if len(current_text) > 0 and stable_count >= 3 and not stop_visible:
                    break
                    
                await asyncio.sleep(check_interval)
                
            self.status = "Connected & Ready"

    async def take_screenshot_base64(self) -> str:
        """Captures a PNG screenshot of the current page and returns it as a Base64 string."""
        if not self.page or self.page.is_closed():
            return ""
        try:
            screenshot_bytes = await self.page.screenshot(type="png")
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        except Exception as e:
            print(f"[WARNING] Failed to capture screenshot: {e}")
            return ""

