/**
 * Web2API Pro - Extension Popup Script for Firefox / Zen
 */

const ext = typeof browser !== "undefined" ? browser : chrome;

// DOM Elements
const bridgeBadge = document.getElementById("bridgeBadge");
const tabBadge = document.getElementById("tabBadge");
const openGeminiBtn = document.getElementById("openGeminiBtn");
const openChatgptBtn = document.getElementById("openChatgptBtn");
const openClaudeBtn = document.getElementById("openClaudeBtn");
const resetChatBtn = document.getElementById("resetChatBtn");
const bridgeUrlInput = document.getElementById("bridgeUrlInput");
const reconnectBridgeBtn = document.getElementById("reconnectBridgeBtn");
const modelSelect = document.getElementById("modelSelect");
const formatSelect = document.getElementById("formatSelect");
const promptInput = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");
const btnIcon = document.getElementById("btnIcon");
const statCount = document.getElementById("statCount");
const copyCurlBtn = document.getElementById("copyCurlBtn");
const latencyBadge = document.getElementById("latencyBadge");
const copyOutputBtn = document.getElementById("copyOutputBtn");
const outputView = document.getElementById("outputView");

let lastResult = null;
let currentBridgeUrl = "ws://127.0.0.1:8000/ws";

// Initialize and refresh status
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

    if (res.bridgeUrl && !bridgeUrlInput.value) {
      bridgeUrlInput.value = res.bridgeUrl;
      currentBridgeUrl = res.bridgeUrl;
    }

    // Active Chat Tab status
    if (res.activeTab) {
      const pName = res.activeTab.platform;
      if (res.activeTab.inputReady) {
        tabBadge.textContent = `${pName}: Ready`;
        tabBadge.className = "badge badge-connected";
      } else {
        tabBadge.textContent = `${pName}: Loading`;
        tabBadge.className = "badge badge-warning";
      }
    } else if (res.hasChatTab) {
      tabBadge.textContent = "Tab: Not Ready";
      tabBadge.className = "badge badge-warning";
    } else {
      tabBadge.textContent = "Tab: Offline";
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
    outputView.textContent = lastResult.choices?.[0]?.message?.content || JSON.stringify(lastResult, null, 2);
  }
}

// Event Listeners
formatSelect.addEventListener("change", renderOutput);

openGeminiBtn.addEventListener("click", () => {
  ext.runtime.sendMessage({ action: "OPEN_CHAT_TAB", platform: "gemini" });
  setTimeout(refreshStatus, 1500);
});

openChatgptBtn.addEventListener("click", () => {
  ext.runtime.sendMessage({ action: "OPEN_CHAT_TAB", platform: "chatgpt" });
  setTimeout(refreshStatus, 1500);
});

openClaudeBtn.addEventListener("click", () => {
  ext.runtime.sendMessage({ action: "OPEN_CHAT_TAB", platform: "claude" });
  setTimeout(refreshStatus, 1500);
});

reconnectBridgeBtn.addEventListener("click", async () => {
  const url = bridgeUrlInput.value.trim();
  if (/^\d{6}$/.test(url)) {
    // 6 digits = pairing code from `python3 web2api_keys.py pair` on the bridge device.
    reconnectBridgeBtn.disabled = true;
    reconnectBridgeBtn.textContent = "...";
    const res = await ext.runtime.sendMessage({ action: "PAIR_WITH_CODE", code: url });
    reconnectBridgeBtn.disabled = false;
    reconnectBridgeBtn.textContent = "Connect";
    bridgeUrlInput.value = "";
    outputView.textContent = res && res.success
      ? "Paired! The extension now connects to the bridge with its key."
      : `Pairing failed: ${(res && res.error) || "unknown error"}`;
    setTimeout(refreshStatus, 1000);
    return;
  }
  if (url) {
    reconnectBridgeBtn.disabled = true;
    reconnectBridgeBtn.textContent = "...";
    await ext.runtime.sendMessage({ action: "SET_BRIDGE_URL", url });
    setTimeout(() => {
      reconnectBridgeBtn.disabled = false;
      reconnectBridgeBtn.textContent = "Connect";
      refreshStatus();
    }, 1000);
  }
});

resetChatBtn.addEventListener("click", async () => {
  resetChatBtn.disabled = true;
  const orig = resetChatBtn.innerHTML;
  resetChatBtn.textContent = "Resetting...";
  try {
    const res = await ext.runtime.sendMessage({
      action: "RUN_POPUP_PROMPT",
      prompt: "RESET_CHAT" // Background routes RESET action
    });
    outputView.textContent = "New conversation thread initiated.";
  } catch (err) {
    outputView.textContent = "Reset error: " + err.message;
  } finally {
    resetChatBtn.disabled = false;
    resetChatBtn.innerHTML = orig;
    refreshStatus();
  }
});

copyCurlBtn.addEventListener("click", () => {
  const selectedModel = modelSelect.value === "auto" ? "gemini-pro" : modelSelect.value;
  const curlCmd = `curl -X POST http://127.0.0.1:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${selectedModel}",
    "messages": [
      {"role": "user", "content": "Write a high-performance Fibonacci function in Rust."}
    ]
  }'`;

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
  outputView.textContent = "Dispatching prompt to active browser chat tab and awaiting response...";
  const startTime = Date.now();

  const selectedModel = modelSelect.value === "auto" ? "pro-web" : modelSelect.value;

  try {
    const res = await ext.runtime.sendMessage({
      action: "RUN_POPUP_PROMPT",
      prompt: prompt,
      model: selectedModel
    });

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    latencyBadge.textContent = `${elapsed}s`;

    if (res && res.success) {
      lastResult = res.data;
      renderOutput();
    } else {
      outputView.textContent = "Error: " + (res?.error || "Execution failed. Ensure an AI chat tab (Gemini, ChatGPT, or Claude) is open and logged in.");
    }
  } catch (err) {
    outputView.textContent = "Request Exception: " + err.message;
  } finally {
    sendBtn.disabled = false;
    btnIcon.textContent = "🚀";
    refreshStatus();
  }
});

// Refresh immediately and periodically
refreshStatus();
setInterval(refreshStatus, 2500);
