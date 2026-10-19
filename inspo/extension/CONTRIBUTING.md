# Contributing to PromptRelay

Thank you for your interest in contributing to PromptRelay! 

To preserve the extension's **zero-ban safety guarantee**, **100% legal compliance**, and **zero cost**, all contributors must strictly adhere to the following architectural constraints.

---

## The Non-Negotiable Core Principles

### 1. Zero External Network Requests
* PRs that introduce any network calls to external servers, analytics trackers, or third-party APIs will be immediately rejected.
* All functionality must remain strictly local within the user's browser.

### 2. User-Initiated Actions Only (No Headless Automation)
* PromptRelay is an **assistive macro and productivity overlay**, NOT a bot.
* All DOM writes and navigation actions must be directly triggered by a physical user click or keyboard shortcut.
* Never implement background auto-submitting loops, automatic prompt polling, or automated request dispatchers.

### 3. No Private API Reverse-Engineering
* Never attempt to intercept, monkeypatch, or replicate private, internal platform APIs (e.g., undocumented endpoints like `/backend-api/*`).
* Do not attempt to bypass Cloudflare, DataDome, Arkose Labs, or Turnstile security challenges.
* Interact only with the visible, rendered Document Object Model (DOM).

### 4. Zero Paywall Bypassing
* The extension must never attempt to unlock paid tiers, bypass subscription verifications, or circumvent model restrictions.
* Its single purpose is facilitating context continuity across legitimate user accounts.

### 5. Multi-Tier Resilient Selectors
* When adding or updating DOM selectors for chat platforms, avoid transient auto-generated CSS hashes (e.g., `.css-19akd2`).
* Use semantic attributes (`[data-message-author-role]`, `textarea`, `[contenteditable="true"]`, `<article>`).
* Always maintain a fallback path so that minor UI changes do not cause hard errors.

---

## Development Workflow

1. Clone your fork of the repository.
2. In Chrome, Edge, or Brave, open `chrome://extensions`.
3. Enable **Developer mode** (top right toggle).
4. Click **Load unpacked** and select the repository directory.
5. Make your code changes.
6. Click the refresh icon on the PromptRelay card in `chrome://extensions` to test your changes.

---

## Code Quality Standards
* Use standard modern Vanilla JavaScript (ES2022+).
* No unnecessary build steps or heavy dependencies unless strictly justified.
* All user-facing styles inside `content/content.css` must use the `cr-` prefix to prevent style pollution with host platforms.
