/**
 * Web2API Firefox Extension - Content Script
 * Directly automates the chat web interface (Gemini/ChatGPT/Claude) in the user's real browser session.
 * Types prompts, observes streaming generation, preserves code blocks, and returns clean API responses.
 */

(function () {
  if (window.__web2api_injected) return;
  window.__web2api_injected = true;

  console.log("[Web2API] Content script loaded on:", window.location.href);

  // Configuration & Selectors
  const SELECTORS = {
    gemini: {
      input: [
        'div[contenteditable="true"]',
        'rich-textarea [contenteditable="true"]',
        'textarea',
        '[data-placeholder*="Ask"]'
      ],
      sendButton: [
        'button[aria-label*="Send" i]',
        'button[aria-label*="send" i]',
        'button.send-button',
        '[data-test-id="send-button"]',
        'button mat-icon[data-mat-icon-name="send"]'
      ],
      stopButton: [
        'button[aria-label*="Stop" i]',
        'button[aria-label*="stop" i]',
        '[data-test-id="stop-button"]'
      ],
      messages: [
        'message-content',
        '.message-content',
        'model-response',
        '.model-response-text',
        'article'
      ],
      newChat: [
        'a[href*="/app"]',
        'button[aria-label*="New chat" i]',
        '[data-test-id="new-chat-button"]',
        'button:has-text("New chat")'
      ]
    },
    generic: {
      input: ['textarea', 'div[contenteditable="true"]', '[role="textbox"]'],
      sendButton: ['button[type="submit"]', 'button[aria-label*="Send" i]'],
      stopButton: ['button[aria-label*="Stop" i]'],
      messages: ['article', '.message', '[data-message-author-role="assistant"]'],
      newChat: ['button[aria-label*="New chat" i]']
    }
  };

  function getPlatformSelectors() {
    const host = window.location.hostname;
    if (host.includes("gemini.google.com")) return SELECTORS.gemini;
    return SELECTORS.generic;
  }

  function findElement(selectorList, parent = document) {
    for (const sel of selectorList) {
      try {
        const el = parent.querySelector(sel);
        if (el) return el;
      } catch (e) {}
    }
    return null;
  }

  function findAllElements(selectorList, parent = document) {
    for (const sel of selectorList) {
      try {
        const list = parent.querySelectorAll(sel);
        if (list && list.length > 0) return Array.from(list);
      } catch (e) {}
    }
    return [];
  }

  /**
   * Simulates realistic human typing and framework events so Angular/React registers input
   */
  async function typePrompt(text) {
    const selectors = getPlatformSelectors();
    const inputEl = findElement(selectors.input);

    if (!inputEl) {
      throw new Error("Chat input box not found. Ensure you are on a supported chat page and logged in.");
    }

    inputEl.focus();

    if (inputEl.isContentEditable) {
      // ContentEditable (Gemini rich-textarea)
      inputEl.innerHTML = "";
      const p = document.createElement("p");
      p.textContent = text;
      inputEl.appendChild(p);

      // Trigger events
      inputEl.dispatchEvent(new Event("beforeinput", { bubbles: true, composed: true }));
      inputEl.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      inputEl.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      inputEl.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "End" }));
    } else {
      // Standard textarea
      inputEl.value = text;
      inputEl.dispatchEvent(new Event("input", { bubbles: true }));
      inputEl.dispatchEvent(new Event("change", { bubbles: true }));
    }

    // Small delay to allow Angular/React UI state to update send button disabled state
    await new Promise(r => setTimeout(r, 200));

    // Try finding send button
    let sendBtn = findElement(selectors.sendButton);
    if (sendBtn && !sendBtn.disabled) {
      // If found parent button from inner icon
      if (sendBtn.tagName.toLowerCase() !== "button") {
        sendBtn = sendBtn.closest("button") || sendBtn;
      }
      sendBtn.click();
    } else {
      // Fallback: Send Enter key
      const enterDown = new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Enter",
        code: "Enter",
        keyCode: 13
      });
      inputEl.dispatchEvent(enterDown);
    }
  }

  /**
   * Monitor streaming output and wait for full completion
   */
  async function waitForResponse(initialMessageCount, timeoutMs = 120000) {
    const selectors = getPlatformSelectors();
    const startTime = Date.now();

    // Wait until response container appears or stop button is visible
    let targetMessage = null;

    while (Date.now() - startTime < 15000) {
      const messages = findAllElements(selectors.messages);
      if (messages.length > initialMessageCount) {
        targetMessage = messages[messages.length - 1];
        break;
      }
      const stopBtn = findElement(selectors.stopButton);
      if (stopBtn) {
        // Response is actively streaming
        const latestMsgs = findAllElements(selectors.messages);
        if (latestMsgs.length > 0) {
          targetMessage = latestMsgs[latestMsgs.length - 1];
          break;
        }
      }
      await new Promise(r => setTimeout(r, 250));
    }

    if (!targetMessage) {
      // Fallback to the latest message element available
      const msgs = findAllElements(selectors.messages);
      if (msgs.length > 0) {
        targetMessage = msgs[msgs.length - 1];
      } else {
        throw new Error("Timed out waiting for response message container to appear.");
      }
    }

    // Stabilization engine: Poll DOM text until it stabilizes and stop button is gone
    let lastText = "";
    let stableSince = Date.now();
    const STABILIZATION_DELAY = 1200; // ms of unchanged text required

    while (Date.now() - startTime < timeoutMs) {
      const currentRawText = targetMessage.innerText || targetMessage.textContent || "";
      const stopBtn = findElement(selectors.stopButton);

      if (currentRawText !== lastText) {
        lastText = currentRawText;
        stableSince = Date.now();
      } else {
        // Text is steady; check if stabilization window has passed and no stop button
        const elapsedSteady = Date.now() - stableSince;
        if (elapsedSteady >= STABILIZATION_DELAY && !stopBtn) {
          // Double-check send button is re-enabled
          const sendBtn = findElement(selectors.sendButton);
          if (!sendBtn || !sendBtn.disabled || elapsedSteady >= 2500) {
            break; // Successfully completed!
          }
        }
      }

      await new Promise(r => setTimeout(r, 300));
    }

    // Convert target message DOM to clean markdown with preserved code blocks
    let markdown = "";
    if (window.Web2APIParser && typeof window.Web2APIParser.domToMarkdown === "function") {
      markdown = window.Web2APIParser.domToMarkdown(targetMessage);
    } else {
      markdown = (targetMessage.innerText || targetMessage.textContent || "").trim();
    }

    return markdown;
  }

  /**
   * Reset conversation by clicking New Chat
   */
  async function resetChat() {
    const selectors = getPlatformSelectors();
    const newChatBtn = findElement(selectors.newChat);
    if (newChatBtn) {
      newChatBtn.click();
      await new Promise(r => setTimeout(r, 1000));
      return true;
    }
    // Alternatively navigate to base app URL
    window.location.href = "https://gemini.google.com/app";
    return true;
  }

  // Handle incoming commands from background script or popup
  const runtime = typeof browser !== "undefined" ? browser.runtime : chrome.runtime;

  runtime.onMessage.addListener((request, sender, sendResponse) => {
    const action = request.action;

    if (action === "PING") {
      const selectors = getPlatformSelectors();
      const input = findElement(selectors.input);
      sendResponse({
        status: "ok",
        url: window.location.href,
        inputReady: !!input,
        title: document.title
      });
      return true;
    }

    if (action === "NEW_CHAT") {
      resetChat()
        .then(() => sendResponse({ success: true, message: "Chat reset initiated" }))
        .catch(err => sendResponse({ success: false, error: err.message }));
      return true;
    }

    if (action === "RUN_PROMPT") {
      (async () => {
        try {
          const selectors = getPlatformSelectors();
          const initialMessages = findAllElements(selectors.messages);
          const initialCount = initialMessages.length;

          // 1. Type and dispatch prompt
          await typePrompt(request.prompt);

          // 2. Wait for full streamed response
          const markdownOutput = await waitForResponse(initialCount, request.timeout || 120000);

          // 3. Parse and structure via Web2APIParser
          let apiResponse;
          if (window.Web2APIParser) {
            apiResponse = window.Web2APIParser.normalizeToApiResponse(markdownOutput, {
              prompt: request.prompt,
              model: request.model || "gemini-pro-web"
            });
          } else {
            apiResponse = {
              choices: [{ message: { role: "assistant", content: markdownOutput } }]
            };
          }

          sendResponse({ success: true, data: apiResponse });
        } catch (err) {
          console.error("[Web2API] Prompt execution failed:", err);
          sendResponse({ success: false, error: err.message });
        }
      })();
      return true; // Keep channel open for async response
    }
  });
})();
