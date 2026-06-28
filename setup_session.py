import asyncio
import os
import sys
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

SESSION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".playwright_session"))

async def run_setup():
    print("=" * 60)
    print("                Gemini Web2API Session Creator")
    print("=" * 60)
    print(f"Session data will be stored in: {SESSION_DIR}\n")
    print("Launching Chromium in HEADFUL mode...")
    
    async with async_playwright() as p:
        # Launch Chromium with a persistent context.
        # This will save all cookies, local storage, and history.
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={"width": 1280, "height": 850},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        
        page = await context.new_page()
        # Add stealth features to make it look like a normal browser
        await stealth_async(page)
        
        print("Opening gemini.google.com...")
        await page.goto("https://gemini.google.com/app")
        
        print("\nACTION REQUIRED:")
        print("1. In the browser window that just opened, log in to your Google account.")
        print("2. Solve any CAPTCHAs, two-factor authentication (2FA), or prompt screens.")
        print("3. Wait until you see the active Gemini chat page.")
        print("4. Once you see the text box ('Enter a prompt here...'), return to this terminal.")
        print("-" * 60)
        
        # Interactive loop to check state and wait for user confirmation
        while True:
            response = input("\nHave you logged in successfully and see the chat input box? (y/n/exit): ").strip().lower()
            if response in ('y', 'yes'):
                # Verify that we can find the textbox
                try:
                    input_box = page.locator('div[contenteditable="true"]').first
                    # Wait up to 3s to verify if it's there
                    await input_box.wait_for(timeout=3000)
                    print("\n[SUCCESS] Detected the Gemini prompt textbox! Session verified.")
                    break
                except Exception:
                    print("\n[WARNING] Could not detect the prompt textbox on the current page.")
                    print("Are you sure you are on the main Gemini chat page (gemini.google.com/app)?")
                    print("Please make sure you are logged in, then try answering 'y' again.")
            elif response == 'exit':
                print("\nExiting session setup without saving verification.")
                break
            else:
                print("\nPlease complete the login in the browser window and then type 'y'.")

        print("Saving session data and closing browser...")
        await context.close()
        print("\nSession saved successfully! You can now start the server with: ./start.sh serve")

if __name__ == "__main__":
    try:
        asyncio.run(run_setup())
    except KeyboardInterrupt:
        print("\nSetup interrupted. Exiting.")
        sys.exit(1)
