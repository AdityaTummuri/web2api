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
        self.session_dir = session_dir
        self.headless = headless
        self.playwright = None
        self.context = None
        self.page = None
        self.lock = asyncio.Lock()
        self.status = "Disconnected"
        self.is_connected = False
        self.last_error = None
        self.last_activity = None
        
        # Selectors
        self.INPUT_SELECTOR = 'div[contenteditable="true"]'
        self.SEND_BUTTON_SELECTOR = 'button[aria-label*="Send" i], button[aria-label*="send" i], button:has-text("Send"), button.send-button'
        self.STOP_BUTTON_SELECTOR = 'button[aria-label*="Stop" i], button[aria-label*="stop" i]'
        self.MESSAGE_SELECTORS = ['message-content', '[class*="message-content"]', '.message-content', 'article']

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
            self.is_connected = False
            self.status = "Awaiting Authentication"
            self.last_error = str(e)
            print(f"[ERROR] Session verification failed: {e}")
            raise
        except Exception as e:
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
                await self.page.evaluate("1 + 1")
                is_healthy = True
            except Exception:
                pass
                
        if not is_healthy:
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
            
            for _ in range(20): # 10 seconds max wait for element creation
                for selector in self.MESSAGE_SELECTORS:
                    cnt = await self.page.locator(selector).count()
                    if cnt > initial_count:
                        # Grab the newly created response element (nth element is 0-indexed, so it's initial_count)
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
                
                # Compare
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
