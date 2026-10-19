# Archive

Superseded material kept for reference only.

* `playwright-gemini/` — the first prototype: a FastAPI server that launched its own headless Chromium
  (Playwright) with a separate Google login. Replaced by the browser-extension + local-bridge design
  because it needed a second login, was easy for sites to detect as a bot, and bound to all network
  interfaces without authentication. See `spec/01-current-state-analysis.md` §4 and `spec/02-loopholes-and-issues.md` (L-03).
  Only its documentation lives here so far; its code files (`server.py`, `session_manager.py`,
  `setup_session.py`, `templates/`, `ask-gemini.sh`) move here in Phase 0 of `spec/10-implementation-plan.md`.
