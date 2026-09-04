/**
 * Web2API Firefox Extension - Background Script
 * Serves as the central bridge between external API clients (via local WebSocket)
 * and the active Gemini chat tab.
 */

// Cross-browser compatibility shim (Firefox supports both browser and chrome)
const ext = typeof browser !== "undefined" ? browser : chrome;

// State
let ws = null;
let wsConnected = false;
let bridgeUrls = ["ws://127.0.0.1:8000/ws", "ws://127.0.0.1:8765"];
let currentUrlIndex = 0;
let reconnectTimer = null;
let currentChatTabId = null;

// Stats
const stats = {
  totalRequests: 0,
  successfulRequests: 0,
  failedRequests: 0,
  lastRequestTime: null
};

// Target URL pattern
const CHAT_URL_PATTERN = "*://gemini.google.com/*";
const DEFAULT_CHAT_URL = "https://gemini.google.com/app";

/**
 * Connect to the local Web2API bridge server via WebSocket
 */
function connectBridge() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return;
  }

  const wsUrl = bridgeUrls[currentUrlIndex];
  console.log(`[Web2API Background] Attempting connection to bridge at ${wsUrl}...`);

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`[Web2API Background] Connected to bridge at ${wsUrl}`);
      wsConnected = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      // Send handshake
      ws.send(JSON.stringify({
        type: "HANDSHAKE",
        client: "firefox-extension",
        version: "2.0.0",
        endpoint: wsUrl
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
      currentUrlIndex = (currentUrlIndex + 1) % bridgeUrls.length;
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      wsConnected = false;
      try { ws.close(); } catch (e) {}
    };
  } catch (err) {
    wsConnected = false;
    currentUrlIndex = (currentUrlIndex + 1) % bridgeUrls.length;
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
 * Finds an open Gemini tab or creates one if none exists
 */
async function getOrCreateChatTab() {
  const tabs = await ext.tabs.query({ url: CHAT_URL_PATTERN });

  if (tabs && tabs.length > 0) {
    currentChatTabId = tabs[0].id;
    return tabs[0];
  }

  // Create new tab pinned in background
  const newTab = await ext.tabs.create({
    url: DEFAULT_CHAT_URL,
    active: false,
    pinned: true
  });

  currentChatTabId = newTab.id;

  // Wait for tab to load
  await new Promise((resolve) => {
    const listener = (tabId, changeInfo) => {
      if (tabId === newTab.id && changeInfo.status === "complete") {
        ext.tabs.onUpdated.removeListener(listener);
        setTimeout(resolve, 2500);
      }
    };
    ext.tabs.onUpdated.addListener(listener);
  });

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
      const tab = await getOrCreateChatTab();
      if (!tab || !tab.id) {
        throw new Error("Could not find or create a Gemini chat tab.");
      }

      // Dispatch prompt to content script
      const response = await ext.tabs.sendMessage(tab.id, {
        action: "RUN_PROMPT",
        prompt: req.prompt,
        model: req.model || "gemini-pro-web",
        timeout: req.timeout || 120000
      });

      if (response && response.success) {
        stats.successfulRequests++;
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
      const tab = await getOrCreateChatTab();
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

// Handle messages from the extension popup
ext.runtime.onMessage.addListener((request, sender, sendResponse) => {
  const action = request.action;

  if (action === "GET_STATUS") {
    (async () => {
      const tabs = await ext.tabs.query({ url: CHAT_URL_PATTERN });
      let tabReady = false;
      let tabTitle = "";

      if (tabs.length > 0) {
        try {
          const tabCheck = await ext.tabs.sendMessage(tabs[0].id, { action: "PING" });
          tabReady = tabCheck && tabCheck.inputReady;
          tabTitle = tabs[0].title || "Gemini Chat";
        } catch (e) {
          tabReady = false;
        }
      }

      sendResponse({
        wsConnected,
        bridgeUrl: bridgeUrls[currentUrlIndex],
        hasChatTab: tabs.length > 0,
        chatTabReady: tabReady,
        chatTabTitle: tabTitle,
        stats
      });
    })();
    return true;
  }

  if (action === "RUN_POPUP_PROMPT") {
    (async () => {
      try {
        const tab = await getOrCreateChatTab();
        const res = await ext.tabs.sendMessage(tab.id, {
          action: "RUN_PROMPT",
          prompt: request.prompt,
          model: request.model || "gemini-pro-web"
        });
        sendResponse(res);
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true;
  }

  if (action === "OPEN_CHAT_TAB") {
    getOrCreateChatTab().then(tab => {
      ext.tabs.update(tab.id, { active: true });
      sendResponse({ success: true, tabId: tab.id });
    });
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
