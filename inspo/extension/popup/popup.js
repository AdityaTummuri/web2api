/**
 * PromptRelay - Popup Controller
 */

document.addEventListener('DOMContentLoaded', async () => {
  setupTabs();
  await loadActiveSessionStatus();
  await loadCapsulesVault();
  await loadSettingsForm();
  bindActions();
});

// Tab navigation
function setupTabs() {
  const tabs = document.querySelectorAll('.cr-tab');
  const panes = document.querySelectorAll('.cr-tab-pane');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      panes.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPane = document.getElementById(tab.getAttribute('data-tab'));
      if (targetPane) targetPane.classList.add('active');
    });
  });
}

// Load status of active browser tab
async function loadActiveSessionStatus() {
  const badge = document.getElementById('active-platform-badge');
  const countEl = document.getElementById('session-count');
  const loadEl = document.getElementById('session-load');
  const windowEl = document.getElementById('session-window');
  const progressFill = document.getElementById('session-progress');
  const alertBanner = document.getElementById('session-alert');

  // Query active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) {
    badge.textContent = 'Non-Chat Page';
    return;
  }

  let platform = 'unknown';
  let platformName = 'Non-Chat Page';
  if (tab.url.includes('chatgpt.com') || tab.url.includes('openai.com')) {
    platform = 'chatgpt';
    platformName = 'ChatGPT';
  } else if (tab.url.includes('claude.ai')) {
    platform = 'claude';
    platformName = 'Claude';
  } else if (tab.url.includes('gemini.google.com')) {
    platform = 'gemini';
    platformName = 'Gemini';
  }

  if (platform === 'unknown') {
    badge.textContent = 'Non-Chat Page';
    return;
  }

  badge.textContent = platformName;
  badge.classList.add('active');

  const settings = await window.ContextStorage.getSettings();
  const threshold = settings.thresholds[platform] || 25;
  const windowHours = settings.windowHours[platform] || 3;
  const count = await window.ContextStorage.getRecentPromptCount(platform, windowHours);

  const ratio = Math.min(100, Math.round((count / threshold) * 100));

  countEl.textContent = count;
  loadEl.textContent = `${ratio}%`;
  windowEl.textContent = `${windowHours}h`;
  progressFill.style.width = `${ratio}%`;

  if (ratio >= (settings.warningPercentage || 80)) {
    alertBanner.style.display = 'block';
  }
}

// Load saved capsules vault
async function loadCapsulesVault() {
  const listEl = document.getElementById('capsule-list');
  const emptyEl = document.getElementById('capsule-empty');
  const badgeCount = document.getElementById('capsule-count');

  const capsules = await window.ContextStorage.getHandoverCapsules();
  badgeCount.textContent = capsules.length;

  if (capsules.length === 0) {
    emptyEl.style.display = 'block';
    return;
  }

  emptyEl.style.display = 'none';
  listEl.innerHTML = '';

  capsules.forEach(cap => {
    const item = document.createElement('div');
    item.className = 'cr-capsule-item';

    const dateStr = new Date(cap.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    item.innerHTML = `
      <div class="cr-capsule-top">
        <span class="cr-capsule-title"></span>
        <span class="cr-capsule-date">${dateStr}</span>
      </div>
      <div class="cr-capsule-preview"></div>
      <div class="cr-capsule-btn-row">
        <button class="cr-sm-btn btn-copy-cap" data-id="${cap.id}">📋 Copy</button>
        <button class="cr-sm-btn btn-dl-cap" data-id="${cap.id}">💾 .md</button>
        <button class="cr-sm-btn btn-tp-cap" data-id="${cap.id}" data-dest="claude">-> Claude</button>
        <button class="cr-sm-btn btn-tp-cap" data-id="${cap.id}" data-dest="chatgpt">-> ChatGPT</button>
        <button class="cr-sm-btn btn-tp-cap" data-id="${cap.id}" data-dest="gemini">-> Gemini</button>
      </div>
    `;

    // Strictly assign untrusted AI context via textContent to prevent HTML/XSS parsing
    item.querySelector('.cr-capsule-title').textContent = cap.title || 'Handover Capsule';
    item.querySelector('.cr-capsule-preview').textContent = cap.content;

    // Copy capsule
    item.querySelector('.btn-copy-cap').addEventListener('click', async () => {
      await navigator.clipboard.writeText(cap.content);
      showToast('Capsule copied to clipboard!');
    });

    // Download as .md
    item.querySelector('.btn-dl-cap').addEventListener('click', () => {
      const blob = new Blob([cap.content], { type: 'text/markdown;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const cleanTitle = (cap.title || 'handover').toLowerCase().replace(/[^a-z0-9]+/g, '-');
      a.download = `${cleanTitle}-${cap.id || Date.now()}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      showToast('Markdown file downloaded!');
    });

    // Teleport from vault
    item.querySelectorAll('.btn-tp-cap').forEach(btn => {
      btn.addEventListener('click', () => {
        const dest = btn.getAttribute('data-dest');
        chrome.runtime.sendMessage({
          action: 'TELEPORT_CONTEXT',
          destination: dest,
          content: cap.content
        });
        showToast(`Teleporting capsule to ${dest}...`);
      });
    });

    listEl.appendChild(item);
  });
}

// Load and bind settings
async function loadSettingsForm() {
  const settings = await window.ContextStorage.getSettings();

  document.getElementById('setting-thresh-chatgpt').value = settings.thresholds.chatgpt || 30;
  document.getElementById('setting-thresh-claude').value = settings.thresholds.claude || 20;
  document.getElementById('setting-thresh-gemini').value = settings.thresholds.gemini || 40;
  document.getElementById('setting-warn-percent').value = settings.warningPercentage || 80;
  document.getElementById('setting-hud-enabled').checked = settings.hudEnabled !== false;

  document.getElementById('settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const updated = {
      ...settings,
      thresholds: {
        chatgpt: parseInt(document.getElementById('setting-thresh-chatgpt').value, 10),
        claude: parseInt(document.getElementById('setting-thresh-claude').value, 10),
        gemini: parseInt(document.getElementById('setting-thresh-gemini').value, 10)
      },
      warningPercentage: parseInt(document.getElementById('setting-warn-percent').value, 10),
      hudEnabled: document.getElementById('setting-hud-enabled').checked
    };

    await window.ContextStorage.saveSettings(updated);
    showToast('Preferences saved successfully!');
    await loadActiveSessionStatus();
  });

  document.getElementById('btn-reset-counters').addEventListener('click', async () => {
    await chrome.storage.local.remove(['cr_prompts']);
    showToast('Counters reset for all platforms.');
    await loadActiveSessionStatus();
  });
}

// Action button handlers
function bindActions() {
  // Inject Handover Prompt button
  document.getElementById('btn-popup-handover').addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;

    chrome.tabs.sendMessage(tab.id, { action: 'INJECT_HANDOVER_PROMPT' }, (res) => {
      if (chrome.runtime.lastError) {
        showToast('Refresh the chat tab to activate PromptRelay.');
      } else {
        showToast('Prompt staged in active chat box!');
      }
    });
  });

  // Save Last Response button
  document.getElementById('btn-popup-capture').addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;

    chrome.tabs.sendMessage(tab.id, { action: 'CAPTURE_LATEST_BRIEF' }, async (res) => {
      if (chrome.runtime.lastError || !res || !res.content) {
        showToast('Could not grab response. Highlight text on page first.');
      } else {
        showToast('Handover capsule saved to vault!');
        await loadCapsulesVault();
      }
    });
  });

  // Teleport cards
  document.querySelectorAll('.cr-teleport-card').forEach(card => {
    card.addEventListener('click', async () => {
      const dest = card.getAttribute('data-dest');
      const latest = await window.ContextStorage.getLatestCapsule();
      
      if (!latest || !latest.content) {
        showToast('No saved capsule found. Save a brief first.');
        return;
      }

      chrome.runtime.sendMessage({
        action: 'TELEPORT_CONTEXT',
        destination: dest,
        content: latest.content
      });
      showToast(`Teleporting latest capsule to ${dest}...`);
    });
  });

  // Clear Vault
  document.getElementById('btn-clear-vault').addEventListener('click', async () => {
    await window.ContextStorage.clearCapsules();
    await loadCapsulesVault();
    showToast('Capsule vault cleared.');
  });
}

function showToast(msg) {
  const toast = document.getElementById('popup-toast');
  toast.textContent = msg;
  toast.style.display = 'block';
  setTimeout(() => {
    toast.style.display = 'none';
  }, 2500);
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
