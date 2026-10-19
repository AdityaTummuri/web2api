# Troubleshooting

Common issues and how to resolve them.

## "Awaiting Authentication" status

**Cause:** The `.playwright_session/` directory doesn't exist, or the saved session is no longer valid (e.g., Google signed you out).

**Fix:** Run `./start.sh auth`, log in in the visible browser window, and confirm the chat page loaded. Then restart the server with `./start.sh serve`.

## "Browser is not connected. Current status: Failed to Start."

**Cause:** The headless browser failed to launch or crashed.

**Fixes:**
- Check the terminal output for the underlying error in `manager.last_error` (also visible via `/api/status`).
- Trigger `/api/reconnect` from the dashboard or `curl -X POST http://localhost:8000/api/reconnect`.
- Ensure your machine has enough memory and that Chromium can run (a display server is not needed for headless, but system libraries may be missing). If Chromium won't launch, install system dependencies via `playwright install-deps chromium`.

## 401 Unauthorized on `/api/chat`

**Cause:** The session is not authenticated (redirected to Google login) or the prompt input box wasn't found.

**Fix:** Re-run `./start.sh auth`. If Google keeps signing you out, re-authenticate to refresh the cookies.

## Request times out / returns partial response

**Cause:** Gemini took longer than `timeout_sec` to stabilize, or the response element selector no longer matches (Gemini UI changes).

**Fixes:**
- Increase `timeout_sec` (up to 180).
- The manager returns the partial text so far with a `[WARNING] Response did not stabilize` message.
- If Gemini changed its DOM, update `MESSAGE_SELECTORS` / `INPUT_SELECTOR` / `SEND_BUTTON_SELECTOR` in `session_manager.py`.

## Concurrency / rate limiting / bot detection

**Cause:** Gemini's web interface is not designed for heavy automation. Sending requests in parallel is prevented by the internal `asyncio.Lock`, but frequent rapid requests can still trigger bot detection.

**Fixes:**
- Keep request rates low (add delays between calls).
- Do not run the headless server while also using the same Google account for other automated tasks.
- If you see Google's "unusual traffic" page, re-authenticate and slow down.

## Screenshot is empty on the dashboard

**Cause:** The browser page is closed or the screenshot failed.

**Fix:** Look at `/api/status` for `is_connected`. Use the "Reconnect Browser" button or `/api/reconnect`.

## Port already in use

**Cause:** Another server is on port 8000.

**Fixes:**
- Set `PORT=9000 ./start.sh serve`, or
- Kill the process using port 8000.

## The dashboard shows "Disconnected" / red dot

**Fix:** Check `/api/status`; use Reconnect; verify the server process is still running.

## Legal / ToS considerations

This tool interacts with Gemini's web UI rather than the official API. Google may change the interface, restrict access, or terminate your session. Use at your own risk and review Google's Terms of Service.
