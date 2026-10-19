/**
 * PromptRelay - Floating HUD Interface
 * Non-intrusive, draggable floating control pill injected into chat interfaces
 */

(function () {
  const HANDOVER_META_PROMPT = `[SYSTEM DIRECTIVE: CONTEXT HANDOVER BRIEF]

We are approaching usage and rate limits for this current AI session. Before our context window resets or access is interrupted, please generate an ultra-dense, comprehensive technical state brief designed to be pasted as the intake prompt for a fresh AI session.

Structure your response EXACTLY using the following sections:

### 1. MISSION & CONSTRAINTS
- Core objective and scope of our work
- Primary technology stack, framework versions, and architectural decisions
- Non-negotiable constraints, rules, and user preferences

### 2. COMPLETED & VERIFIED
- Components, modules, or files created, modified, and verified
- Specific problems or bugs that were successfully diagnosed and solved

### 3. ACTIVE PROBLEM / CURRENT STATE
- Exactly what we are working on right at this moment
- Current blockers, active error traces, or incomplete code blocks
- Relevant code snippets or configuration state needed to continue

### 4. IMMEDIATE NEXT ACTIONS
- The exact step-by-step task the new AI session should execute first
- Pending items waiting in the queue

Conclude your response with this exact marker line:
--- HANDOVER CAPSULE READY ---`;

  // Inline CSS rules directly inside Shadow DOM to guarantee immunity from host CSP style-src restrictions
  const HUD_STYLES = `
    :host { all: initial !important; }
    #cr-hud-root {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 2147483647;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #f3f4f6;
      user-select: none;
      font-size: 13px;
      line-height: 1.4;
      box-sizing: border-box;
    }
    #cr-hud-root * { box-sizing: border-box; }
    .cr-pill {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(18, 20, 29, 0.85);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 9999px;
      padding: 6px 14px;
      cursor: grab;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35), 0 2px 6px rgba(0, 0, 0, 0.2);
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .cr-pill:hover {
      transform: translateY(-2px);
      border-color: rgba(99, 102, 241, 0.5);
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
    }
    .cr-pill:active { cursor: grabbing; }
    .cr-status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
      transition: background 0.3s ease;
    }
    .cr-status-caution .cr-status-dot {
      background: #f59e0b;
      box-shadow: 0 0 10px rgba(245, 158, 11, 0.8);
    }
    .cr-status-critical .cr-status-dot {
      background: #ef4444;
      box-shadow: 0 0 12px rgba(239, 68, 68, 0.9);
      animation: cr-pulse-red 1.5s infinite;
    }
    @keyframes cr-pulse-red {
      0% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.3); opacity: 0.7; }
      100% { transform: scale(1); opacity: 1; }
    }
    .cr-pill-label { font-weight: 500; color: #e5e7eb; }
    .cr-icon-btn {
      background: transparent;
      border: none;
      color: #9ca3af;
      cursor: pointer;
      padding: 2px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 4px;
      transition: color 0.15s ease, transform 0.2s ease;
    }
    .cr-icon-btn:hover { color: #ffffff; }
    .cr-expanded .cr-icon-btn svg { transform: rotate(180deg); }
    .cr-panel {
      display: none;
      position: absolute;
      bottom: calc(100% + 12px);
      right: 0;
      width: 320px;
      background: rgba(15, 17, 26, 0.94);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.05);
      animation: cr-fade-in 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .cr-expanded .cr-panel { display: block; }
    @keyframes cr-fade-in {
      from { opacity: 0; transform: translateY(8px) scale(0.97); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    .cr-panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .cr-panel-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: #ffffff;
    }
    .cr-platform-badge {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 2px 8px;
      border-radius: 9999px;
      background: rgba(99, 102, 241, 0.18);
      color: #a5b4fc;
      border: 1px solid rgba(99, 102, 241, 0.3);
    }
    .cr-meter-container { margin-bottom: 16px; }
    .cr-meter-info {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: #9ca3af;
      margin-bottom: 6px;
    }
    .cr-meter-bar {
      height: 6px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 9999px;
      overflow: hidden;
    }
    .cr-meter-fill {
      height: 100%;
      background: linear-gradient(90deg, #10b981, #6366f1);
      border-radius: 9999px;
      transition: width 0.3s ease;
    }
    .cr-status-caution .cr-meter-fill { background: linear-gradient(90deg, #f59e0b, #ea580c); }
    .cr-status-critical .cr-meter-fill { background: linear-gradient(90deg, #ef4444, #dc2626); }
    .cr-warning-banner {
      margin-top: 8px;
      padding: 6px 10px;
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.3);
      border-radius: 8px;
      font-size: 11px;
      color: #fca5a5;
    }
    .cr-action-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 14px;
    }
    .cr-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      padding: 9px 14px;
      border-radius: 10px;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.2s ease;
    }
    .cr-btn-primary {
      background: #6366f1;
      color: #ffffff;
      box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3);
    }
    .cr-btn-primary:hover {
      background: #4f46e5;
      box-shadow: 0 6px 18px rgba(99, 102, 241, 0.45);
    }
    .cr-pulse-attention { animation: cr-pulse-btn 1.4s infinite; }
    @keyframes cr-pulse-btn {
      0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6); }
      70% { transform: scale(1.02); box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
      100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }
    .cr-btn-secondary {
      background: rgba(255, 255, 255, 0.06);
      color: #e5e7eb;
      border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .cr-btn-secondary:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #ffffff;
    }
    .cr-teleport-section {
      padding-top: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
    }
    .cr-section-label {
      font-size: 10.5px;
      font-weight: 700;
      letter-spacing: 0.06em;
      color: #9ca3af;
      margin-bottom: 8px;
    }
    .cr-teleport-buttons {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .cr-chip {
      flex: 1 1 auto;
      padding: 6px 10px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 8px;
      font-size: 11.5px;
      font-weight: 500;
      color: #d1d5db;
      cursor: pointer;
      text-align: center;
      transition: all 0.15s ease;
    }
    .cr-chip:hover {
      background: rgba(99, 102, 241, 0.2);
      border-color: rgba(99, 102, 241, 0.4);
      color: #ffffff;
      transform: translateY(-1px);
    }
    .cr-chip-copy {
      flex: 1 1 auto;
      margin-top: 4px;
      background: rgba(16, 185, 129, 0.12);
      border-color: rgba(16, 185, 129, 0.3);
      color: #6ee7b7;
    }
    .cr-chip-copy:hover {
      background: rgba(16, 185, 129, 0.22);
      color: #a7f3d0;
    }
    .cr-chip-dl {
      flex: 1 1 auto;
      margin-top: 4px;
      background: rgba(59, 130, 246, 0.12);
      border-color: rgba(59, 130, 246, 0.3);
      color: #93c5fd;
    }
    .cr-chip-dl:hover {
      background: rgba(59, 130, 246, 0.22);
      color: #bfdbfe;
    }
    .cr-status-msg {
      display: none;
      margin-top: 10px;
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 11.5px;
      text-align: center;
      animation: cr-fade-in 0.2s ease;
    }
    .cr-status-msg.cr-success {
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #a7f3d0;
    }
    .cr-status-msg.cr-error {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #fca5a5;
    }
  `;

  let hudHost = null;
  let hudShadow = null;
  let hudRoot = null;
  let isExpanded = false;
  let currentCapsule = null;

  async function initHUD() {
    // Only inject if detector found a supported platform
    const platform = window.ContextDetector ? window.ContextDetector.getPlatform() : 'unknown';
    if (platform === 'unknown') return;

    // Check if HUD enabled in settings
    if (window.ContextStorage) {
      const settings = await window.ContextStorage.getSettings();
      if (!settings.hudEnabled) return;
    }

    if (document.getElementById('cr-hud-host')) return;

    // 1. Host element appended to body
    hudHost = document.createElement('div');
    hudHost.id = 'cr-hud-host';
    document.body.appendChild(hudHost);

    // 2. Attach closed shadow root - prevents host scripts from querying or tampering with the HUD
    hudShadow = hudHost.attachShadow({ mode: 'closed' });

    // 3. Inject scoped stylesheet into shadow boundary via inline style (immune to host CSP)
    const styleEl = document.createElement('style');
    styleEl.textContent = HUD_STYLES;
    hudShadow.appendChild(styleEl);

    // 4. Create root HUD container inside shadow boundary
    hudRoot = document.createElement('div');
    hudRoot.id = 'cr-hud-root';
    hudRoot.className = 'cr-hud cr-status-normal';
    hudShadow.appendChild(hudRoot);

    renderHUD();
    makeDraggable(hudRoot);

    // Initialize tracker
    if (window.ContextTracker) {
      window.ContextTracker.init();
      window.ContextTracker.onUpdate(updateHUDState);
    }

    // Check if background service worker forwarded a teleported context to this new tab
    checkPendingTeleport();
  }

  function renderHUD() {
    const platformName = window.ContextDetector ? window.ContextDetector.getPlatformName() : 'AI';

    hudRoot.innerHTML = `
      <div class="cr-pill" id="cr-pill-toggle">
        <span class="cr-status-dot"></span>
        <span class="cr-pill-label" id="cr-pill-label"></span>
        <button class="cr-icon-btn" id="cr-btn-expand" title="Open PromptRelay">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="18 15 12 9 6 15"></polyline>
          </svg>
        </button>
      </div>

      <div class="cr-panel" id="cr-panel">
        <div class="cr-panel-header">
          <div class="cr-panel-title">
            <span class="cr-logo-icon">🔄</span>
            <strong>PromptRelay</strong>
          </div>
          <span class="cr-platform-badge" id="cr-platform-badge"></span>
        </div>

        <div class="cr-meter-container">
          <div class="cr-meter-info">
            <span id="cr-meter-text">Session Load: 0%</span>
            <span id="cr-meter-count">0 / 25 msgs</span>
          </div>
          <div class="cr-meter-bar">
            <div class="cr-meter-fill" id="cr-meter-fill" style="width: 0%"></div>
          </div>
          <div class="cr-warning-banner" id="cr-warning-banner" style="display: none;">
            ⚠️ Rate limit alert detected on page!
          </div>
        </div>

        <div class="cr-action-group">
          <button class="cr-btn cr-btn-primary" id="cr-btn-handover" title="Inject prompt asking AI to summarize itself">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
            </svg>
            Ask for Handover Brief
          </button>
          
          <button class="cr-btn cr-btn-secondary" id="cr-btn-capture" title="Grab the latest response and save as context capsule">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
              <polyline points="17 21 17 13 7 13 7 21"></polyline>
              <polyline points="7 3 7 8 15 8"></polyline>
            </svg>
            Save Latest Brief
          </button>
        </div>

        <div class="cr-teleport-section" id="cr-teleport-section" style="display: none;">
          <div class="cr-section-label">TELEPORT CONTEXT TO:</div>
          <div class="cr-teleport-buttons">
            <button class="cr-chip" data-dest="claude">Claude</button>
            <button class="cr-chip" data-dest="chatgpt">ChatGPT</button>
            <button class="cr-chip" data-dest="gemini">Gemini</button>
            <button class="cr-chip cr-chip-copy" id="cr-btn-copy-clip">📋 Copy</button>
            <button class="cr-chip cr-chip-dl" id="cr-btn-dl-md">💾 Save .md</button>
          </div>
        </div>

        <div class="cr-status-msg" id="cr-status-msg"></div>
      </div>
    `;

    hudRoot.querySelector('#cr-pill-label').textContent = `${platformName}: 0 prompts`;
    hudRoot.querySelector('#cr-platform-badge').textContent = platformName;

    bindEvents();
  }

  function bindEvents() {
    const toggle = hudRoot.querySelector('#cr-pill-toggle');
    const panel = hudRoot.querySelector('#cr-panel');
    const handoverBtn = hudRoot.querySelector('#cr-btn-handover');
    const captureBtn = hudRoot.querySelector('#cr-btn-capture');
    const copyBtn = hudRoot.querySelector('#cr-btn-copy-clip');
    const dlBtn = hudRoot.querySelector('#cr-btn-dl-md');
    const teleportChips = hudRoot.querySelectorAll('.cr-chip[data-dest]');

    toggle.addEventListener('click', (e) => {
      // Don't toggle if dragging
      if (hudRoot.dataset.isDragging === 'true') return;
      isExpanded = !isExpanded;
      hudRoot.classList.toggle('cr-expanded', isExpanded);
    });

    handoverBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (window.ContextInjector) {
        const ok = window.ContextInjector.injectText(HANDOVER_META_PROMPT);
        if (ok) {
          showStatus('Handover prompt staged! Review & hit Enter.', 'success');
        } else {
          showStatus('Could not find input box. Focus it manually.', 'error');
        }
      }
    });

    captureBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!window.ContextExtractor) return;

      const briefText = window.ContextExtractor.extractLatestResponseText();
      if (!briefText || briefText.length < 50) {
        showStatus('No response found. Highlight the text first.', 'error');
        return;
      }

      const platform = window.ContextDetector ? window.ContextDetector.getPlatform() : 'chat';
      const title = window.ContextDetector ? window.ContextDetector.getConversationTitle() : 'Session';

      const capsule = {
        sourcePlatform: platform,
        title: title,
        content: briefText
      };

      if (window.ContextStorage) {
        currentCapsule = await window.ContextStorage.saveHandoverCapsule(capsule);
      }

      hudRoot.querySelector('#cr-teleport-section').style.display = 'block';
      showStatus('Brief saved! Choose target AI to teleport.', 'success');
    });

    copyBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const content = currentCapsule ? currentCapsule.content : (window.ContextExtractor ? window.ContextExtractor.extractLatestResponseText() : '');
      if (!content) {
        showStatus('No content to copy.', 'error');
        return;
      }
      try {
        await navigator.clipboard.writeText(content);
        showStatus('Copied capsule to clipboard!', 'success');
      } catch (err) {
        showStatus('Clipboard permission failed.', 'error');
      }
    });

    if (dlBtn) {
      dlBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const content = currentCapsule ? currentCapsule.content : (window.ContextExtractor ? window.ContextExtractor.extractLatestResponseText() : '');
        if (!content) {
          showStatus('Save a brief first before downloading.', 'error');
          return;
        }
        const platform = window.ContextDetector ? window.ContextDetector.getPlatform() : 'chat';
        downloadMarkdownFile(`handover-${platform}-${Date.now()}.md`, content);
        showStatus('Markdown file downloaded!', 'success');
      });
    }

    teleportChips.forEach(chip => {
      chip.addEventListener('click', (e) => {
        e.stopPropagation();
        const dest = chip.getAttribute('data-dest');
        const content = currentCapsule ? currentCapsule.content : (window.ContextExtractor ? window.ContextExtractor.extractLatestResponseText() : '');
        
        if (!content) {
          showStatus('Save a brief first before teleporting.', 'error');
          return;
        }

        // Ask background service worker to open destination tab and pass context
        chrome.runtime.sendMessage({
          action: 'TELEPORT_CONTEXT',
          destination: dest,
          content: content
        }, (res) => {
          showStatus(`Teleporting to ${dest}...`, 'success');
        });
      });
    });
  }

  function updateHUDState(state) {
    if (!hudRoot) return;

    hudRoot.className = `cr-hud cr-status-${state.status}` + (isExpanded ? ' cr-expanded' : '');

    const label = hudRoot.querySelector('#cr-pill-label');
    const meterText = hudRoot.querySelector('#cr-meter-text');
    const meterCount = hudRoot.querySelector('#cr-meter-count');
    const meterFill = hudRoot.querySelector('#cr-meter-fill');
    const warningBanner = hudRoot.querySelector('#cr-warning-banner');

    const pName = window.ContextDetector ? window.ContextDetector.getPlatformName() : 'AI';

    if (label) label.textContent = `${pName}: ${state.count} prompts`;
    if (meterText) meterText.textContent = `Load: ${state.ratio}%`;
    if (meterCount) meterCount.textContent = `${state.count} / ${state.threshold} msgs`;
    if (meterFill) meterFill.style.width = `${state.ratio}%`;

    if (warningBanner) {
      warningBanner.style.display = state.hasWarningBanner ? 'block' : 'none';
    }

    if (state.status === 'critical' || state.hasWarningBanner) {
      hudRoot.querySelector('#cr-btn-handover').classList.add('cr-pulse-attention');
    } else {
      hudRoot.querySelector('#cr-btn-handover').classList.remove('cr-pulse-attention');
    }
  }

  function showStatus(msg, type = 'info') {
    const statusEl = hudRoot.querySelector('#cr-status-msg');
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.className = `cr-status-msg cr-${type}`;
    statusEl.style.display = 'block';
    setTimeout(() => {
      statusEl.style.display = 'none';
    }, 4000);
  }

  async function checkPendingTeleport() {
    // Check if background worker has a pending staged context for this platform
    const platform = window.ContextDetector ? window.ContextDetector.getPlatform() : 'unknown';
    chrome.runtime.sendMessage({ action: 'GET_PENDING_TELEPORT', platform }, async (response) => {
      if (response && response.content) {
        // Poll for target input element mounting (handles slow cold starts & Cloudflare challenges up to 7.5s)
        const inputEl = window.ContextExtractor
          ? await window.ContextExtractor.waitForInputElement(30, 250)
          : null;

        if (window.ContextInjector) {
          const ok = window.ContextInjector.injectText(response.content, inputEl);
          showStatus('Teleported context staged! Review & hit Enter.', ok ? 'success' : 'error');
        }
      }
    });
  }

  function downloadMarkdownFile(filename, content) {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || `handover-${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function makeDraggable(el) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    const header = el.querySelector('#cr-pill-toggle');

    header.onmousedown = dragMouseDown;

    function dragMouseDown(e) {
      if (e.target.closest('button')) return;
      e.preventDefault();
      pos3 = e.clientX;
      pos4 = e.clientY;
      document.onmouseup = closeDragElement;
      document.onmousemove = elementDrag;
      el.dataset.isDragging = 'false';
    }

    function elementDrag(e) {
      e.preventDefault();
      el.dataset.isDragging = 'true';
      pos1 = pos3 - e.clientX;
      pos2 = pos4 - e.clientY;
      pos3 = e.clientX;
      pos4 = e.clientY;
      el.style.top = (el.offsetTop - pos2) + 'px';
      el.style.left = (el.offsetLeft - pos1) + 'px';
      el.style.bottom = 'auto';
      el.style.right = 'auto';
    }

    function closeDragElement() {
      document.onmouseup = null;
      document.onmousemove = null;
      setTimeout(() => { el.dataset.isDragging = 'false'; }, 50);
    }
  }

  // Listen for actions dispatched from the extension popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'INJECT_HANDOVER_PROMPT') {
      if (window.ContextInjector) {
        const ok = window.ContextInjector.injectText(HANDOVER_META_PROMPT);
        showStatus('Handover prompt staged! Review & hit Enter.', ok ? 'success' : 'error');
        sendResponse({ success: ok });
      } else {
        sendResponse({ success: false });
      }
      return false;
    }

    if (request.action === 'CAPTURE_LATEST_BRIEF') {
      if (window.ContextExtractor) {
        const briefText = window.ContextExtractor.extractLatestResponseText();
        if (briefText && briefText.length > 40) {
          const platform = window.ContextDetector ? window.ContextDetector.getPlatform() : 'chat';
          const title = window.ContextDetector ? window.ContextDetector.getConversationTitle() : 'Session';
          window.ContextStorage.saveHandoverCapsule({
            sourcePlatform: platform,
            title,
            content: briefText
          }).then((cap) => {
            currentCapsule = cap;
            showStatus('Capsule saved to vault!', 'success');
            sendResponse({ success: true, content: briefText });
          });
          return true; // async sendResponse
        }
      }
      sendResponse({ success: false });
      return false;
    }
  });

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHUD);
  } else {
    initHUD();
  }
})();
