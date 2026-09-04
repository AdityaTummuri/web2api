/**
 * Web2API Pro - Extension Popup Script
 */

const ext = typeof browser !== "undefined" ? browser : chrome;

// DOM Elements
const bridgeBadge = document.getElementById("bridgeBadge");
const tabBadge = document.getElementById("tabBadge");
const openTabBtn = document.getElementById("openTabBtn");
const resetChatBtn = document.getElementById("resetChatBtn");
const copyCurlBtn = document.getElementById("copyCurlBtn");
const promptInput = document.getElementById("promptInput");
const formatSelect = document.getElementById("formatSelect");
const sendBtn = document.getElementById("sendBtn");
const btnIcon = document.getElementById("btnIcon");
const statCount = document.getElementById("statCount");
const latencyBadge = document.getElementById("latencyBadge");
const copyOutputBtn = document.getElementById("copyOutputBtn");
const outputView = document.getElementById("outputView");

let lastResult = null;

// Initialize status
async function refreshStatus() {
  try {
    const res = await ext.runtime.sendMessage({ action: "GET_STATUS" });
    if (!res) return;

    // Bridge status
    if (res.wsConnected) {
      bridgeBadge.textContent = "Bridge: Connected";
      bridgeBadge.className = "badge badge-connected";
    } else {
      bridgeBadge.textContent = "Bridge: Offline";
      bridgeBadge.className = "badge badge-disconnected";
    }

    // Chat tab status
    if (res.chatTabReady) {
      tabBadge.textContent = "Tab: Ready";
      tabBadge.className = "badge badge-connected";
    } else if (res.hasChatTab) {
      tabBadge.textContent = "Tab: Not Ready";
      tabBadge.className = "badge badge-warning";
    } else {
      tabBadge.textContent = "Tab: Not Found";
      tabBadge.className = "badge badge-disconnected";
    }

    // Stats
    if (res.stats) {
      statCount.textContent = res.stats.totalRequests || 0;
    }
  } catch (err) {
    console.warn("Could not fetch status:", err);
  }
}

// Update output view according to selected format
function renderOutput() {
  if (!lastResult) return;

  const mode = formatSelect.value;
  if (mode === "openai") {
    outputView.textContent = JSON.stringify(lastResult, null, 2);
  } else if (mode === "code") {
    const blocks = lastResult.extracted?.code_blocks || [];
    if (blocks.length === 0) {
      outputView.textContent = "// No explicit code blocks detected in response.\n\n" + (lastResult.choices?.[0]?.message?.content || "");
    } else {
      outputView.textContent = blocks
        .map(b => `// Language: ${b.language}\n${b.code}`)
        .join("\n\n// ----------------------------------------\n\n");
    }
  } else if (mode === "markdown") {
    outputView.textContent = lastResult.choices?.[0]?.message?.content || JSON.stringify(lastResult);
  }
}

// Event Listeners
formatSelect.addEventListener("change", renderOutput);

openTabBtn.addEventListener("click", () => {
  ext.runtime.sendMessage({ action: "OPEN_CHAT_TAB" });
  setTimeout(refreshStatus, 1500);
});

resetChatBtn.addEventListener("click", async () => {
  resetChatBtn.disabled = true;
  resetChatBtn.textContent = "Resetting...";
  try {
    const tabs = await ext.tabs.query({ url: "*://gemini.google.com/*" });
    if (tabs.length > 0) {
      await ext.tabs.sendMessage(tabs[0].id, { action: "NEW_CHAT" });
      outputView.textContent = "Conversation thread successfully reset.";
    } else {
      outputView.textContent = "No active Gemini tab found to reset.";
    }
  } catch (err) {
    outputView.textContent = "Reset error: " + err.message;
  } finally {
    resetChatBtn.disabled = false;
    resetChatBtn.innerHTML = "<span>🔄</span> New Chat Thread";
  }
});

copyCurlBtn.addEventListener("click", () => {
  const curlCmd = `curl -X POST http://127.0.0.1:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{"model": "gemini-pro", "messages": [{"role": "user", "content": "Write a fast Fibonacci function in Rust"}]}'`;

  navigator.clipboard.writeText(curlCmd);
  const orig = copyCurlBtn.innerHTML;
  copyCurlBtn.innerHTML = "<span>✓</span> Copied!";
  setTimeout(() => (copyCurlBtn.innerHTML = orig), 2000);
});

copyOutputBtn.addEventListener("click", () => {
  const text = outputView.textContent;
  if (!text) return;
  navigator.clipboard.writeText(text);
  copyOutputBtn.textContent = "Copied!";
  setTimeout(() => (copyOutputBtn.textContent = "Copy"), 2000);
});

sendBtn.addEventListener("click", async () => {
  const prompt = promptInput.value.trim();
  if (!prompt) return;

  sendBtn.disabled = true;
  btnIcon.textContent = "⏳";
  outputView.textContent = "Typing into Gemini chat and awaiting response...";
  const startTime = Date.now();

  try {
    const res = await ext.runtime.sendMessage({
      action: "RUN_POPUP_PROMPT",
      prompt: prompt,
      model: "gemini-pro-web"
    });

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    latencyBadge.textContent = `${elapsed}s`;

    if (res && res.success) {
      lastResult = res.data;
      renderOutput();
    } else {
      outputView.textContent = "Error: " + (res?.error || "Execution failed. Ensure Gemini tab is open and logged in.");
    }
  } catch (err) {
    outputView.textContent = "Request Exception: " + err.message;
  } finally {
    sendBtn.disabled = false;
    btnIcon.textContent = "🚀";
    refreshStatus();
  }
});

// Refresh immediately and on focus
refreshStatus();
setInterval(refreshStatus, 3000);
