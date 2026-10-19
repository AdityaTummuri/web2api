/**
 * PromptRelay - Background Service Worker
 * Coordinates cross-tab teleportation and context staging
 */

// URL endpoints for fresh chat creation
const PLATFORM_URLS = {
  chatgpt: 'https://chatgpt.com/',
  claude: 'https://claude.ai/new',
  gemini: 'https://gemini.google.com/app'
};

// Storage session area helper (survives SW termination cycles, auto-clears on browser close)
const getSessionStorage = () => chrome.storage.session || chrome.storage.local;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'TELEPORT_CONTEXT') {
    const dest = message.destination;
    const content = message.content;

    if (dest && PLATFORM_URLS[dest]) {
      const storageArea = getSessionStorage();
      const key = `teleport_${dest}`;
      const payload = {
        content: content,
        timestamp: Date.now()
      };

      storageArea.set({ [key]: payload }, () => {
        chrome.tabs.create({ url: PLATFORM_URLS[dest], active: true }, (tab) => {
          sendResponse({ success: true, tabId: tab.id });
        });
      });

      return true; // Keep message channel open for async response
    }

    sendResponse({ success: false, error: 'Unknown destination platform' });
    return false;
  }

  if (message.action === 'GET_PENDING_TELEPORT') {
    const platform = message.platform;
    const key = `teleport_${platform}`;
    const storageArea = getSessionStorage();

    storageArea.get([key], (data) => {
      const pending = data[key];

      // Check if there is an active teleport payload less than 60 seconds old
      if (pending && (Date.now() - pending.timestamp < 60000)) {
        storageArea.remove(key); // Atomic single-use claim
        sendResponse({ content: pending.content });
      } else {
        sendResponse({ content: null });
      }
    });

    return true; // Keep channel open for async response
  }

  if (message.action === 'UPDATE_BADGE') {
    const count = message.count || 0;
    const text = count > 0 ? String(count) : '';
    chrome.action.setBadgeText({ text });
    chrome.action.setBadgeBackgroundColor({ color: message.color || '#6366f1' });
    sendResponse({ success: true });
    return false;
  }
});
