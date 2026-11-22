/**
 * Web2API Pro Firefox / Zen Extension - Content Script
 * Directly automates the chat web interfaces (Gemini, ChatGPT, Claude) in the user's authentic browser session.
 * Types prompts, observes streaming generation, preserves code blocks, and returns clean API responses.
 */

(function () {
  if (window.__web2api_injected) return;
  window.__web2api_injected = true;

  console.log("[Web2API] Content script loaded on:", window.location.href);

  // Platform Selector Registry
  const SELECTORS = {
    gemini: {
      input: [
        'rich-textarea div[contenteditable="true"]',
        'div[contenteditable="true"]',
        'div.ql-editor[contenteditable="true"]',
        'div[role="textbox"][contenteditable="true"]',
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
        '[data-test-id="stop-button"]',
        'mat-icon[data-mat-icon-name="stop"]'
      ],
      messages: [
        'message-content',
        '.message-content',
        'model-response',
        '.model-response-text',
        '.response-container',
        'article'
      ],
      newChat: [
        'a[href*="/app"]',
        'button[aria-label*="New chat" i]',
        '[data-test-id="new-chat-button"]',
        'button:has-text("New chat")'
      ]
    },
    chatgpt: {
      input: [
        '#prompt-textarea',
        'div[id="prompt-textarea"][contenteditable="true"]',
        'textarea[data-id="root"]',
        'div[contenteditable="true"][data-placeholder]',
        'div.ProseMirror[contenteditable]',
        'form [contenteditable]:not([contenteditable="false"])',
        '[role="textbox"]',
        'textarea',
        '[contenteditable]:not([contenteditable="false"])'
      ],
      sendButton: [
        'button[data-testid="send-button"]',
        '#composer-submit-button',
        'button[aria-label*="Send" i]',
        'button[aria-label*="submit" i]'
      ],
      stopButton: [
        'button[data-testid="stop-button"]',
        'button[aria-label*="Stop" i]'
      ],
      messages: [
        '[data-message-author-role="assistant"]',
        '[data-testid^="conversation-turn"] .markdown',
        'div.agent-turn',
        '.markdown.prose',
        '.markdown',
        '.prose',
        'article'
      ],
      newChat: [
        'a[href="/"]',
        'button[aria-label*="New chat" i]',
        '[data-testid="new-chat-button"]'
      ]
    },
    claude: {
      input: [
        'div[contenteditable="true"].ProseMirror',
        'div[data-testid="chat-input"] [contenteditable="true"]',
        'fieldset div[contenteditable="true"]',
        'div[contenteditable="true"]'
      ],
      sendButton: [
        'button[aria-label*="Send Message" i]',
        'button[aria-label*="Send message" i]',
        'button[aria-label*="Send" i]',
        'fieldset button:not([disabled])'
      ],
      stopButton: [
        'button[aria-label*="Stop" i]',
        'button[data-testid="stop-generating"]'
      ],
      messages: [
        '[data-is-streaming]',
        '.font-claude-message',
        'div[data-testid="chat-message"]',
        '.grid-cols-1 .whitespace-pre-wrap',
        'article'
      ],
      newChat: [
        'a[href="/new"]',
        'button[aria-label*="Start new chat" i]',
        'button[aria-label*="New chat" i]'
      ]
    },
    generic: {
      input: [
        'div[role="textbox"][contenteditable="true"]',
        'div[contenteditable="true"]',
        'textarea',
        'input[type="text"]'
      ],
      sendButton: [
        'button[type="submit"]',
        'button[aria-label*="Send" i]',
        'button[aria-label*="Submit" i]'
      ],
      stopButton: [
        'button[aria-label*="Stop" i]'
      ],
      messages: [
        'article',
        '.message',
        '[data-message-author-role="assistant"]'
      ],
      newChat: [
        'button[aria-label*="New chat" i]'
      ]
    }
  };

  function detectPlatform() {
    const host = window.location.hostname;
    if (host.includes("gemini.google.com")) return "gemini";
    if (host.includes("chatgpt.com") || host.includes("openai.com")) return "chatgpt";
    if (host.includes("claude.ai")) return "claude";
    return "generic";
  }

  function getPlatformSelectors() {
    const p = detectPlatform();
    return SELECTORS[p] || SELECTORS.generic;
  }

  function shadowRoots(root = document) {
    const roots = [];
    const walk = (node) => {
      for (const el of node.querySelectorAll("*")) {
        if (el.shadowRoot) { roots.push(el.shadowRoot); walk(el.shadowRoot); }
      }
    };
    try { walk(root); } catch (e) {}
    return roots;
  }

  function findElement(selectorList, parent = document) {
    if (!selectorList) return null;
    const scopes = [parent];
    let shadowsLoaded = false;
    for (let i = 0; i < scopes.length || !shadowsLoaded; i++) {
      if (i >= scopes.length) { scopes.push(...shadowRoots(parent)); shadowsLoaded = true; if (i >= scopes.length) break; }
      for (const sel of selectorList) {
        try {
          const el = scopes[i].querySelector(sel);
          if (el && isElementVisible(el)) return el;
        } catch (e) {}
      }
    }
    return null;
  }

  async function waitForElement(selectorList, timeoutMs = 10000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const el = findElement(selectorList);
      if (el) return el;
      await new Promise(r => setTimeout(r, 400));
    }
    return null;
  }

  // Same-origin iframes (some mobile layouts render the thread inside one).
  function frameDocuments(root = document) {
    const docs = [];
    for (const f of root.querySelectorAll("iframe")) {
      try { if (f.contentDocument && f.contentDocument.body) docs.push(f.contentDocument); } catch (e) {}
    }
    return docs;
  }

  function findAllElements(selectorList, parent = document) {
    if (!selectorList) return [];
    const scopes = parent === document ? [document, ...frameDocuments(), ...shadowRoots()] : [parent];
    for (const sel of selectorList) {
      for (const scope of scopes) {
        try {
          const list = scope.querySelectorAll(sel);
          if (list && list.length > 0) return Array.from(list);
        } catch (e) {}
      }
    }
    return [];
  }

  // Compact page diagnostics for error messages (no page text, only structure).
  function describeInputs(selectorList) {
    const q = (sel) => { try { return document.querySelectorAll(sel).length; } catch (e) { return -1; } };
    const testids = Array.from(new Set(Array.from(document.querySelectorAll("[data-testid]")).map(e => e.getAttribute("data-testid")))).slice(0, 12);
    const editables = Array.from(document.querySelectorAll("[contenteditable]")).slice(0, 3)
      .map(e => `${e.tagName.toLowerCase()}#${e.id || "-"}.${(e.className || "").toString().split(" ").slice(0, 2).join(".")}[ce=${e.getAttribute("contenteditable")}]`);
    const parts = [
      `url=${location.origin}${location.pathname}`,
      `ready=${document.readyState}`,
      `vis=${document.visibilityState}`,
      `ua=${/Android/.test(navigator.userAgent) ? "android" : "desktop"}`,
      `w=${window.innerWidth}`,
      `els=${q("*")}`,
      `textarea=${q("textarea")}`,
      `ce=${q("[contenteditable]")}`,
      `textbox=${q("[role=textbox]")}`,
      `input=${q("input")}`,
      `form=${q("form")}`,
      `iframe=${q("iframe")}`,
      `frames=[${Array.from(document.querySelectorAll("iframe")).slice(0, 3).map(f => {
        let info = "";
        try { const d = f.contentDocument; info = d ? `same-origin,els=${d.querySelectorAll("*").length},text=${(d.body && d.body.innerText || "").length}` : "cross-origin"; } catch (e) { info = "cross-origin"; }
        return `${(f.getAttribute("src") || "about:blank").slice(0, 60)}(${info},${f.offsetWidth}x${f.offsetHeight})`;
      }).join(" ")}]`,
      `main=${(document.querySelector("main") && document.querySelector("main").innerText || "").length}`,
      `shadow=${shadowRoots().length}`,
      `bodyText=${(document.body && document.body.innerText || "").length}`,
      `editables=[${editables.join(" ")}]`,
      `testids=[${testids.join(",")}]`
    ];
    for (const sel of selectorList || []) {
      try {
        const all = Array.from(document.querySelectorAll(sel));
        if (!all.length) continue;
        const shown = all.filter(isElementVisible).length;
        const st = window.getComputedStyle(all[0]);
        parts.push(`${sel}:${all.length}/${shown}vis(d=${st.display},v=${st.visibility},o=${st.opacity})`);
      } catch (e) {}
    }
    return parts.join(" ");
  }

  function isElementVisible(el) {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
  }

  /**
   * Resilient text insertion handling ProseMirror (Claude), Lexical (ChatGPT),
   * Angular Quill (Gemini), and standard textareas.
   */
  async function typePrompt(text) {
    const selectors = getPlatformSelectors();
    const inputEl = await waitForElement(selectors.input);

    if (!inputEl) {
      throw new Error(`Chat input box not found on ${detectPlatform().toUpperCase()}. Ensure you are logged in and on the chat page. [diag: ${describeInputs(selectors.input)}]`);
    }

    inputEl.focus();

    const isEditable = inputEl.isContentEditable || inputEl.getAttribute("contenteditable") === "true";

    if (isEditable) {
      // 1. Synthetic ClipboardEvent: ProseMirror & Lexical handle this cleanly
      let inserted = false;
      try {
        const dt = new DataTransfer();
        dt.setData("text/plain", text);
        const pasteEvent = new ClipboardEvent("paste", {
          clipboardData: dt,
          bubbles: true,
          cancelable: true
        });
        const prevented = !inputEl.dispatchEvent(pasteEvent);
        if (prevented || inputEl.textContent.includes(text.slice(0, Math.min(20, text.length)))) {
          inserted = true;
        }
      } catch (e) {
        console.warn("[Web2API] Synthetic paste fallback:", e);
      }

      // 2. Fallback: execCommand('insertText')
      if (!inserted) {
        try {
          const selection = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(inputEl);
          selection.removeAllRanges();
          selection.addRange(range);
          inserted = document.execCommand("insertText", false, text);
        } catch (e) {}
      }

      // 3. Fallback: Direct DOM node insertion + InputEvent
      if (!inserted || !inputEl.textContent.trim()) {
        inputEl.innerHTML = "";
        const p = document.createElement("p");
        p.textContent = text;
        inputEl.appendChild(p);

        inputEl.dispatchEvent(new InputEvent("input", {
          bubbles: true,
          cancelable: true,
          inputType: "insertText",
          data: text
        }));
      }

      // Framework trigger events
      inputEl.dispatchEvent(new Event("beforeinput", { bubbles: true, composed: true }));
      inputEl.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      inputEl.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      inputEl.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "End" }));
    } else {
      // Standard textarea
      inputEl.focus();
      let inserted = false;
      try {
        inserted = document.execCommand("insertText", false, text);
      } catch (e) {}

      if (!inserted) {
        inputEl.value = text;
      }

      inputEl.dispatchEvent(new Event("input", { bubbles: true }));
      inputEl.dispatchEvent(new Event("change", { bubbles: true }));
    }

    // Wait for framework state to enable the send button
    let sendBtn = null;
    const btnStartTime = Date.now();
    while (Date.now() - btnStartTime < 1500) {
      sendBtn = findElement(selectors.sendButton);
      if (sendBtn) {
        if (sendBtn.tagName.toLowerCase() !== "button") {
          sendBtn = sendBtn.closest("button") || sendBtn;
        }
        const isDisabled = sendBtn.disabled || sendBtn.getAttribute("aria-disabled") === "true";
        if (!isDisabled) {
          break;
        }
      }
      await new Promise(r => setTimeout(r, 100));
    }

    // Click send button if ready
    if (sendBtn && !sendBtn.disabled && sendBtn.getAttribute("aria-disabled") !== "true") {
      sendBtn.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true, cancelable: true }));
      sendBtn.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      sendBtn.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
      sendBtn.click();
    } else {
      // Fallback: Dispatch Enter key event
      const enterOptions = {
        bubbles: true,
        cancelable: true,
        key: "Enter",
        code: "Enter",
        which: 13,
        keyCode: 13
      };
      inputEl.dispatchEvent(new KeyboardEvent("keydown", enterOptions));
      inputEl.dispatchEvent(new KeyboardEvent("keypress", enterOptions));
      inputEl.dispatchEvent(new KeyboardEvent("keyup", enterOptions));
    }
  }

  /**
   * Monitor streaming output and wait for full completion
   */
  async function waitForResponse(initialMessageCount, timeoutMs = 120000) {
    const selectors = getPlatformSelectors();
    const startTime = Date.now();

    let targetMessage = null;

    // Step 1: Wait until a new response starts streaming or message container appears
    while (Date.now() - startTime < 15000) {
      const messages = findAllElements(selectors.messages);
      if (messages.length > initialMessageCount) {
        targetMessage = messages[messages.length - 1];
        break;
      }
      const stopBtn = findElement(selectors.stopButton);
      if (stopBtn) {
        const latestMsgs = findAllElements(selectors.messages);
        if (latestMsgs.length > 0) {
          targetMessage = latestMsgs[latestMsgs.length - 1];
          break;
        }
      }
      await new Promise(r => setTimeout(r, 200));
    }

    if (!targetMessage) {
      const msgs = findAllElements(selectors.messages);
      if (msgs.length > 0) {
        targetMessage = msgs[msgs.length - 1];
      } else {
        throw new Error(`Timed out waiting for response message container to appear. [diag: ${describeInputs(selectors.messages)} roles=[${Array.from(new Set(Array.from(document.querySelectorAll("[data-message-author-role]")).map(e => e.getAttribute("data-message-author-role")))).join(",")}] articles=${document.querySelectorAll("article").length} turns=${document.querySelectorAll("[data-testid^=conversation-turn]").length}]`);
      }
    }

    // Step 2: Stabilization engine - Poll DOM text until it stabilizes and stop button disappears
    let lastText = "";
    let stableSince = Date.now();
    const STABILIZATION_DELAY = 1200; // ms of unchanged text required

    while (Date.now() - startTime < timeoutMs) {
      // Re-query latest message in case container was re-rendered
      const currentMsgs = findAllElements(selectors.messages);
      if (currentMsgs.length > 0) {
        targetMessage = currentMsgs[currentMsgs.length - 1];
      }

      const currentRawText = (targetMessage.innerText || targetMessage.textContent || "").trim();
      const stopBtn = findElement(selectors.stopButton);

      if (currentRawText !== lastText) {
        lastText = currentRawText;
        stableSince = Date.now();
      } else if (currentRawText.length > 0) {
        const elapsedSteady = Date.now() - stableSince;
        if (elapsedSteady >= STABILIZATION_DELAY && !stopBtn) {
          const sendBtn = findElement(selectors.sendButton);
          const sendReady = !sendBtn || (!sendBtn.disabled && sendBtn.getAttribute("aria-disabled") !== "true");
          if (sendReady || elapsedSteady >= 2500) {
            break; // Finished streaming!
          }
        }
      }

      await new Promise(r => setTimeout(r, 250));
    }

    // Step 3: Convert target message DOM to clean markdown with preserved code blocks
    let markdown = "";
    if (window.Web2APIParser && typeof window.Web2APIParser.domToMarkdown === "function") {
      markdown = window.Web2APIParser.domToMarkdown(targetMessage);
    } else {
      markdown = (targetMessage.innerText || targetMessage.textContent || "").trim();
    }

    if (!markdown && lastText) {
      markdown = lastText;
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
      await new Promise(r => setTimeout(r, 800));
      return true;
    }
    const platform = detectPlatform();
    if (platform === "gemini") window.location.href = "https://gemini.google.com/app";
    else if (platform === "chatgpt") window.location.href = "https://chatgpt.com/";
    else if (platform === "claude") window.location.href = "https://claude.ai/new";
    return true;
  }

  // Cross-browser runtime listener
  const runtime = typeof browser !== "undefined" ? browser.runtime : chrome.runtime;

  runtime.onMessage.addListener((request, sender, sendResponse) => {
    const action = request.action;

    if (action === "PING") {
      const selectors = getPlatformSelectors();
      const input = findElement(selectors.input);
      sendResponse({
        status: "ok",
        platform: detectPlatform(),
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

          // Deep Research activation for Gemini & research modes
          if (request.model && (request.model.includes("deep-research") || request.mode === "deep-research")) {
            try {
              const researchButtons = document.querySelectorAll(
                'button[aria-label*="Deep Research" i], button[aria-label*="research" i], [data-test-id*="deep-research"], [aria-label*="Tools" i]'
              );
              for (const btn of researchButtons) {
                if (isElementVisible(btn) && btn.getAttribute("aria-pressed") !== "true") {
                  btn.click();
                  await new Promise(r => setTimeout(r, 300));
                }
              }
            } catch (e) {
              console.warn("[Web2API] Deep Research toggle attempt:", e);
            }
          }

          // 1. Type and dispatch prompt
          await typePrompt(request.prompt);

          // 2. Wait for full streamed response
          const markdownOutput = await waitForResponse(initialCount, request.timeout || 120000);

          // 3. Parse and structure via Web2APIParser
          let apiResponse;
          if (window.Web2APIParser) {
            apiResponse = window.Web2APIParser.normalizeToApiResponse(markdownOutput, {
              prompt: request.prompt,
              model: request.model || `${detectPlatform()}-web-pro`
            });
          } else {
            apiResponse = {
              choices: [{ message: { role: "assistant", content: markdownOutput } }]
            };
          }

          sendResponse({ success: true, data: apiResponse, platform: detectPlatform() });
        } catch (err) {
          console.error("[Web2API] Prompt execution failed:", err);
          sendResponse({ success: false, error: err.message, platform: detectPlatform() });
        }
      })();
      return true;
    }
  });
})();
