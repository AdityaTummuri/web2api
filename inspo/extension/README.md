# PromptRelay 🔄

> **Seamless AI Context Handover & Session Bridge across ChatGPT, Claude, and Gemini.**  
> *Zero APIs • Zero External Servers • 100% Local Browser Memory • 100% Free & Legal*

---

## ⚡ The Problem It Solves

When working on complex coding, debugging, or writing projects with AI assistants:
1. **Model limits suddenly run out** (e.g., Claude's 5-hour message cap or ChatGPT's GPT-4o rate window).
2. You get locked out mid-task and are forced to switch to a fresh chat or another AI model.
3. Starting a new session normally means **losing all active context, project constraints, and architectural decisions**, forcing you to waste 15 minutes manually re-explaining the problem.

**PromptRelay** acts as your conversational flight recorder and bridge:
* ⏱️ **Monitors your prompt activity** and calculates rolling usage windows.
* ⚠️ **Alerts you before your quota exhausts** so you don't get locked out unexpectedly.
* 🧠 **Prompts the active AI to generate an ultra-dense, structured handover brief** before the last message window expires.
* 🚀 **Teleports the context into a fresh chat or another AI with 1 click**, staging the prompt so you can hit Enter and continue without missing a beat.

---

## 🛡️ 100% Legal & Safety Architecture

PromptRelay is built strictly within the legal and technical boundaries of modern web standards and platform Terms of Service:

| Principle | How PromptRelay Enforces It |
| :--- | :--- |
| **No Headless Botting** | PromptRelay is an assistive clipboard and staging tool. It **never** auto-submits prompts without your manual confirmation. You always review and press Enter yourself. |
| **No Private API Hacking** | Does not intercept, scrape, or spoof private backend API endpoints. It reads only the rendered HTML elements visible on your screen, identical to assistive extensions like Grammarly or screen readers. |
| **Zero External Network Calls** | No third-party servers, no telemetry, no tracking. All session counters and handover capsules live 100% in your browser's `chrome.storage.local`. |
| **Zero Cost Guarantee** | 100% free forever. Requires no API keys, no paid subscriptions, and no cloud hosting. |
| **Multi-Tier Resilient Selectors** | Uses semantic HTML and multi-tier fallback waterfalls so that minor CSS updates by OpenAI, Anthropic, or Google do not break your workflow. |

---

## 🏗️ Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ACTIVE CHAT TAB                                 │
│          (ChatGPT / Claude / Gemini Web Client)                        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
               ┌───────────────────┴───────────────────┐
               ▼                                       ▼
    ┌──────────────────────┐                ┌──────────────────────┐
    │  Passive Tracker     │                │   Warning Detector   │
    │  - Rolling message   │                │   - Catches quota    │
    │    window count      │                │     warning banners  │
    └──────────┬───────────┘                └──────────┬───────────┘
               │                                       │
               └───────────────────┬───────────────────┘
                                   │ (Threshold reached / Alert)
                                   ▼
        ┌─────────────────────────────────────────────────────┐
        │             Floating HUD / Action Button            │
        │             [ 🔄 Ask for Handover Brief ]           │
        └──────────────────────────┬──────────────────────────┘
                                   │ (User Click)
                                   ▼
        ┌─────────────────────────────────────────────────────┐
        │  Stages Engineered Meta-Prompt into Chat Textarea   │
        │  AI outputs high-density state summary              │
        └──────────────────────────┬──────────────────────────┘
                                   │ (AI Finishes Output)
                                   ▼
        ┌─────────────────────────────────────────────────────┐
        │         Stores Capsule in Local Memory              │
        │      [ 🚀 Open in Claude ] [ 🚀 Open in ChatGPT ]   │
        └──────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        TARGET CHAT TAB                                 │
│  Opens destination tab, stages the handover capsule in prompt box.     │
│  You review and hit Enter to immediately resume work!                  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation (Takes 60 Seconds)

Because PromptRelay is designed for personal privacy and zero cost, it does not require installation through third-party stores.

1. **Clone or Download this repository:**
   ```bash
   git clone https://github.com/your-username/prompt-relay.git
   ```
   *(Or download and extract the ZIP archive).*

2. **Open your browser's extension manager:**
   * Google Chrome: Navigate to `chrome://extensions`
   * Brave Browser: Navigate to `brave://extensions`
   * Microsoft Edge: Navigate to `edge://extensions`

3. **Enable Developer Mode:**
   * Toggle the **Developer mode** switch in the top right corner.

4. **Load the Extension:**
   * Click the **Load unpacked** button in the top left.
   * Select this project directory (`/path/to/prompt-relay`).

5. **Done!** Open [ChatGPT](https://chatgpt.com), [Claude](https://claude.ai), or [Gemini](https://gemini.google.com) to see the PromptRelay HUD in action.

---

## 💡 How to Use

### 1. The Floating HUD
When visiting any supported AI chat interface, a minimal, translucent status pill appears in the bottom right corner.
* Displays your **session prompt counter** (e.g. `14 / 25 msgs`).
* Turns **amber** at 80% quota threshold.
* Turns **red** if a platform quota warning banner is detected on page.

### 2. Generating a Handover Capsule
1. Click **"Ask for Handover Brief"** on the floating HUD or open the extension popup.
2. PromptRelay stages a proven, ultra-dense state query into your prompt box.
3. Hit **Enter**. The AI formats the entire project history into a standard state brief.
4. Click **"Save Latest Brief"** once the AI finishes answering.

### 3. Teleporting or Exporting to Markdown
* **Option A (Teleport):** Click one of the teleport buttons (**"Claude"**, **"ChatGPT"**, or **"Gemini"**). PromptRelay opens a fresh session in a new tab, automatically stages your project state brief in the input box, and focuses the cursor.
* **Option B (Download .md):** Click **"💾 Save .md"** to immediately save the handover capsule to your computer as a clean markdown file for VS Code, Cursor, or git.

---

## ⚙️ Configuration

Click the PromptRelay icon in your browser toolbar to open the settings panel:
* **Custom Alert Thresholds:** Set conservative message limits for free tiers (e.g. 15 messages) or relaxed limits for Pro/Plus tiers (e.g. 45 messages).
* **Rolling Window Durations:** Configure time windows (e.g., 3 hours for ChatGPT, 5 hours for Claude).
* **Capsule Vault:** View and export your recent handover capsules directly to your system clipboard or as `.md` files.

---

## ⚖️ Legal Notice & Trademark Disclaimer

* **Independent Project:** PromptRelay is an independent open-source productivity project and is not affiliated, associated, authorized, endorsed by, or in any way officially connected with OpenAI, Anthropic, Google, or any of their subsidiaries or affiliates.
* **Trademarks:** The names *ChatGPT*, *Claude*, and *Gemini*, as well as related names, marks, emblems, and images, are registered trademarks of their respective owners. Their mention in this repository is strictly for identification and descriptive interoperability purposes under fair use.
* **Liability:** This software is provided free of charge under the **MIT License** on an "AS IS" basis, without warranties of any kind. See [LICENSE](LICENSE) for full details.

---

## 📄 License

Distributed under the [MIT License](LICENSE). 100% Free and Open Source.
