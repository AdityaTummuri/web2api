/**
 * Web2API Firefox / Zen Extension - Background Script
 * Serves as the central bridge between external API clients (via local WebSocket)
 * and active browser AI chat tabs (Gemini, ChatGPT, Claude).
 */

const ext = typeof browser !== "undefined" ? browser : chrome;

// Supported Platform Configurations
const PLATFORMS = {
  gemini: {
    id: "gemini",
    name: "Gemini",
    matches: ["*://gemini.google.com/*"],
    url: "https://gemini.google.com/app",
    modelKeywords: ["gemini"]
  },
  chatgpt: {
    id: "chatgpt",
    name: "ChatGPT",
    matches: ["*://chatgpt.com/*", "*://chat.openai.com/*"],
    url: "https://chatgpt.com/",
    modelKeywords: ["gpt", "chatgpt", "o1", "o3"]
  },
  claude: {
    id: "claude",
    name: "Claude",
    matches: ["*://claude.ai/*"],
    url: "https://claude.ai/new",
    modelKeywords: ["claude", "sonnet", "haiku", "opus"]
  }
};

// State
let ws = null;
let wsConnected = false;
let currentBridgeUrl = "ws://127.0.0.1:8000/ws";
const candidateBridgeUrls = [
  "ws://127.0.0.1:8000/ws",
  "ws://127.0.0.1:8787/ws/extension",
  "ws://127.0.0.1:8787/ws",
  "ws://127.0.0.1:8765"
];
let candidateIndex = 0;
let reconnectTimer = null;

// Stats
const stats = {
  totalRequests: 0,
  successfulRequests: 0,
  failedRequests: 0,
  lastRequestTime: null,
  activePlatform: null
};

/**
 * Initialize bridge URL from storage or fallback list
 */
async function getTargetBridgeUrl() {
  try {
    const data = await ext.storage.local.get("customBridgeUrl");
    if (data && data.customBridgeUrl) {
      return data.customBridgeUrl;
    }
  } catch (e) {}
  return candidateBridgeUrls[candidateIndex];
}

/**
 * Connect to the local Web2API bridge server via WebSocket
 */
async function connectBridge() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return;
  }

  currentBridgeUrl = await getTargetBridgeUrl();
  console.log(`[Web2API Background] Connecting to bridge at ${currentBridgeUrl}...`);

  try {
    ws = new WebSocket(currentBridgeUrl);

    ws.onopen = () => {
      console.log(`[Web2API Background] Connected successfully to ${currentBridgeUrl}`);
      wsConnected = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      ws.send(JSON.stringify({
        type: "HANDSHAKE",
        client: "firefox-extension",
        browser: "firefox-zen",
        version: ext.runtime.getManifest().version,
        endpoint: currentBridgeUrl
      }));
    };

    ws.onmessage = async (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log("[Web2API Background] Incoming bridge request:", message);
        await handleBridgeRequest(message);
      } catch (err) {
        console.error("[Web2API Background] Error handling bridge message:", err);
      }
    };

    ws.onclose = () => {
      wsConnected = false;
      candidateIndex = (candidateIndex + 1) % candidateBridgeUrls.length;
      scheduleReconnect();
    };

    ws.onerror = () => {
      wsConnected = false;
      try { ws.close(); } catch (e) {}
    };
  } catch (err) {
    wsConnected = false;
    candidateIndex = (candidateIndex + 1) % candidateBridgeUrls.length;
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (!reconnectTimer) {
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectBridge();
    }, 2500);
  }
}

/**
 * Ensures content script is injected even into tabs opened before the extension was loaded
 */
async function ensureContentScriptInjected(tabId) {
  // Android (Firefox for Android) freezes background tabs: messages and script
  // injection into them fail. Bring the chat tab to the front before using it.
  try {
    const tab = await ext.tabs.get(tabId);
    if (tab && (!tab.active || tab.discarded)) {
      await ext.tabs.update(tabId, { active: true });
      await new Promise(r => setTimeout(r, tab.discarded ? 3000 : 600));
    }
  } catch (e) {}

  try {
    const ping = await ext.tabs.sendMessage(tabId, { action: "PING" });
    if (ping && ping.status === "ok") return true;
  } catch (e) {}

  // Tab does not have content script yet; inject dynamically
  try {
    if (ext.scripting && ext.scripting.executeScript) {
      await ext.scripting.executeScript({
        target: { tabId },
        files: ["parser.js", "content.js"]
      });
    } else if (ext.tabs.executeScript) {
      await ext.tabs.executeScript(tabId, { file: "parser.js" });
      await ext.tabs.executeScript(tabId, { file: "content.js" });
    }
    // Give script a moment to initialize, then confirm it answers
    await new Promise(r => setTimeout(r, 300));
    const ping = await ext.tabs.sendMessage(tabId, { action: "PING" }).catch(() => null);
    if (ping && ping.status === "ok") return true;
    // Orphaned/frozen page (e.g. after an extension update): reload it once
    await ext.tabs.reload(tabId);
    await new Promise(r => setTimeout(r, 4000));
    return true;
  } catch (err) {
    console.warn("[Web2API Background] Dynamic injection failed for tab:", tabId, err);
    return false;
  }
}

/**
 * Resolve target platform based on requested model name
 */
function resolvePlatformFromModel(modelName = "") {
  const m = modelName.toLowerCase();
  for (const [key, p] of Object.entries(PLATFORMS)) {
    if (p.modelKeywords.some(kw => m.includes(kw))) {
      return key;
    }
  }
  return null;
}

/**
 * Finds an open chat tab or creates one
 */
async function getOrCreateChatTab(requestedModel = "") {
  const preferredPlatformKey = resolvePlatformFromModel(requestedModel);

  // If a specific platform is requested, look for its tab first
  if (preferredPlatformKey) {
    const p = PLATFORMS[preferredPlatformKey];
    for (const matchPattern of p.matches) {
      const tabs = await ext.tabs.query({ url: matchPattern });
      if (tabs && tabs.length > 0) {
        await ensureContentScriptInjected(tabs[0].id);
        stats.activePlatform = p.name;
        return tabs[0];
      }
    }
  }

  // Next, look for ANY already open chat tab (Gemini, ChatGPT, or Claude)
  for (const [key, p] of Object.entries(PLATFORMS)) {
    for (const matchPattern of p.matches) {
      const tabs = await ext.tabs.query({ url: matchPattern });
      if (tabs && tabs.length > 0) {
        await ensureContentScriptInjected(tabs[0].id);
        stats.activePlatform = p.name;
        return tabs[0];
      }
    }
  }

  // None open: create a new tab for preferred platform (or Gemini by default)
  const targetPlatform = preferredPlatformKey ? PLATFORMS[preferredPlatformKey] : PLATFORMS.gemini;
  stats.activePlatform = targetPlatform.name;

  const newTab = await ext.tabs.create({
    url: targetPlatform.url,
    active: false,
    pinned: true
  });

  // Wait for tab to complete loading
  await new Promise((resolve) => {
    const listener = (tabId, changeInfo) => {
      if (tabId === newTab.id && changeInfo.status === "complete") {
        ext.tabs.onUpdated.removeListener(listener);
        setTimeout(resolve, 2000);
      }
    };
    ext.tabs.onUpdated.addListener(listener);
  });

  await ensureContentScriptInjected(newTab.id);
  return newTab;
}

/**
 * Handle incoming API execution requests from the WebSocket bridge
 */
async function handleBridgeRequest(req) {
  const reqId = req.id;
  const action = req.action || req.type;

  if (action === "PING") {
    sendBridgeResponse({ id: reqId, status: "success", message: "pong" });
    return;
  }

  if (action === "CHAT" || action === "PROMPT") {
    stats.totalRequests++;
    stats.lastRequestTime = new Date().toISOString();

    try {
      const tab = await getOrCreateChatTab(req.model);
      if (!tab || !tab.id) {
        throw new Error("Could not find or create a supported AI chat tab.");
      }

      await ensureContentScriptInjected(tab.id);

      const response = await ext.tabs.sendMessage(tab.id, {
        action: "RUN_PROMPT",
        prompt: req.prompt,
        model: req.model || "pro-web",
        timeout: req.timeout || 120000
      });

      if (response && response.success) {
        stats.successfulRequests++;
        stats.activePlatform = response.platform || stats.activePlatform;
        sendBridgeResponse({
          id: reqId,
          status: "success",
          data: response.data
        });
      } else {
        stats.failedRequests++;
        sendBridgeResponse({
          id: reqId,
          status: "error",
          error: response ? response.error : "Content script returned unsuccessful response"
        });
      }
    } catch (err) {
      stats.failedRequests++;
      console.error("[Web2API Background] Execution failed:", err);
      sendBridgeResponse({
        id: reqId,
        status: "error",
        error: err.message
      });
    }
  }

  if (action === "RESET") {
    try {
      const tab = await getOrCreateChatTab(req.model);
      await ensureContentScriptInjected(tab.id);
      const response = await ext.tabs.sendMessage(tab.id, { action: "NEW_CHAT" });
      sendBridgeResponse({ id: reqId, status: "success", data: response });
    } catch (err) {
      sendBridgeResponse({ id: reqId, status: "error", error: err.message });
    }
  }
}

function sendBridgeResponse(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

/**
 * Popup and Runtime Message Dispatcher
 */
ext.runtime.onMessage.addListener((request, sender, sendResponse) => {
  const action = request.action;

  if (action === "GET_STATUS") {
    (async () => {
      let openTabsCount = 0;
      let activeTabInfo = null;

      for (const [key, p] of Object.entries(PLATFORMS)) {
        for (const matchPattern of p.matches) {
          const tabs = await ext.tabs.query({ url: matchPattern });
          if (tabs && tabs.length > 0) {
            openTabsCount += tabs.length;
            if (!activeTabInfo) {
              await ensureContentScriptInjected(tabs[0].id);
              try {
                const check = await ext.tabs.sendMessage(tabs[0].id, { action: "PING" });
                activeTabInfo = {
                  platform: p.name,
                  id: tabs[0].id,
                  title: tabs[0].title || p.name,
                  inputReady: check?.inputReady || false
                };
              } catch (e) {
                activeTabInfo = {
                  platform: p.name,
                  id: tabs[0].id,
                  title: tabs[0].title || p.name,
                  inputReady: false
                };
              }
            }
          }
        }
      }

      sendResponse({
        wsConnected,
        bridgeUrl: currentBridgeUrl,
        hasChatTab: openTabsCount > 0,
        activeTab: activeTabInfo,
        stats
      });
    })();
    return true;
  }

  if (action === "RUN_POPUP_PROMPT") {
    (async () => {
      try {
        const tab = await getOrCreateChatTab(request.model);
        await ensureContentScriptInjected(tab.id);
        const res = await ext.tabs.sendMessage(tab.id, {
          action: "RUN_PROMPT",
          prompt: request.prompt,
          model: request.model || "pro-web"
        });
        sendResponse(res);
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true;
  }

  if (action === "OPEN_CHAT_TAB") {
    const platformKey = request.platform || "gemini";
    const targetPlatform = PLATFORMS[platformKey] || PLATFORMS.gemini;
    (async () => {
      // Check if already open
      for (const pattern of targetPlatform.matches) {
        const existing = await ext.tabs.query({ url: pattern });
        if (existing && existing.length > 0) {
          await ext.tabs.update(existing[0].id, { active: true });
          sendResponse({ success: true, tabId: existing[0].id });
          return;
        }
      }
      const newTab = await ext.tabs.create({ url: targetPlatform.url, active: true });
      sendResponse({ success: true, tabId: newTab.id });
    })();
    return true;
  }

  if (action === "SET_BRIDGE_URL") {
    (async () => {
      const newUrl = request.url;
      if (newUrl) {
        await ext.storage.local.set({ customBridgeUrl: newUrl });
      } else {
        await ext.storage.local.remove("customBridgeUrl");
      }
      if (ws) ws.close();
      connectBridge();
      sendResponse({ success: true });
    })();
    return true;
  }

  if (action === "PAIR_WITH_CODE") {
    (async () => {
      // Swap a 6-digit code (from `web2api_keys.py pair` on this device) for the bridge URL + key.
      const ports = [8000, 8787];
      try {
        const cur = new URL((await getTargetBridgeUrl()).replace(/^ws/, "http"));
        if (cur.port && !ports.includes(Number(cur.port))) ports.unshift(Number(cur.port));
      } catch (e) {}
      let lastError = "Bridge server not reachable on this device.";
      for (const port of ports) {
        try {
          const res = await fetch(`http://127.0.0.1:${port}/pair`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code: request.code })
          });
          const data = await res.json().catch(() => ({}));
          if (res.ok && data.bridge_url) {
            await ext.storage.local.set({ customBridgeUrl: data.bridge_url });
            if (ws) ws.close();
            connectBridge();
            sendResponse({ success: true });
            return;
          }
          lastError = (data.error && data.error.message) || data.detail || `Pairing failed (HTTP ${res.status}).`;
          if (res.status !== 404) break;
        } catch (e) {
          // try next port
        }
      }
      sendResponse({ success: false, error: lastError });
    })();
    return true;
  }

  if (action === "RECONNECT_BRIDGE") {
    if (ws) ws.close();
    connectBridge();
    sendResponse({ success: true });
    return true;
  }
});

// Auto-start bridge connection
connectBridge();
