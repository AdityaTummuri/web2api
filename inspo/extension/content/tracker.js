/**
 * PromptRelay - Usage Tracker & Rate Limit Detector
 * Observes user prompts and scans for platform rate-limit warning banners
 */

const ContextTracker = {
  platform: 'unknown',
  promptCount: 0,
  threshold: 25,
  windowHours: 3,
  warningPercent: 80,
  hasWarningBanner: false,
  listeners: [],

  /**
   * Initializes the usage tracker and DOM observers
   */
  async init() {
    this.platform = window.ContextDetector ? window.ContextDetector.getPlatform() : 'unknown';
    if (this.platform === 'unknown') return;

    // Load settings
    if (window.ContextStorage) {
      const settings = await window.ContextStorage.getSettings();
      this.threshold = settings.thresholds[this.platform] || 25;
      this.windowHours = settings.windowHours[this.platform] || 3;
      this.warningPercent = settings.warningPercentage || 80;
      
      // Calculate current rolling count
      this.promptCount = await window.ContextStorage.getRecentPromptCount(this.platform, this.windowHours);
      this._notifyListeners();
    }

    this._setupInputListeners();
    this._setupWarningScanner();
  },

  /**
   * Registers state change listener
   */
  onUpdate(callback) {
    this.listeners.push(callback);
    // Initial call
    callback(this.getState());
  },

  /**
   * Current tracking state
   */
  getState() {
    const ratio = (this.promptCount / Math.max(1, this.threshold)) * 100;
    let status = 'normal'; // 'normal' | 'caution' | 'critical'
    
    if (this.hasWarningBanner || ratio >= 100) {
      status = 'critical';
    } else if (ratio >= this.warningPercent) {
      status = 'caution';
    }

    return {
      platform: this.platform,
      count: this.promptCount,
      threshold: this.threshold,
      windowHours: this.windowHours,
      ratio: Math.min(100, Math.round(ratio)),
      status,
      hasWarningBanner: this.hasWarningBanner
    };
  },

  /**
   * Watches for user submission triggers (Enter key and click on Send buttons)
   */
  _setupInputListeners() {
    let lastLoggedTime = 0;

    const handleSubmission = () => {
      const now = Date.now();
      // Debounce submissions within 2 seconds
      if (now - lastLoggedTime < 2000) return;
      lastLoggedTime = now;

      setTimeout(async () => {
        if (window.ContextStorage) {
          await window.ContextStorage.logPrompt(this.platform);
          this.promptCount = await window.ContextStorage.getRecentPromptCount(this.platform, this.windowHours);
          this._notifyListeners();
        }
      }, 500);
    };

    // Global keydown capture for Enter on inputs
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        const input = window.ContextExtractor ? window.ContextExtractor.findInputElement() : null;
        if (input && (e.target === input || input.contains(e.target))) {
          handleSubmission();
        }
      }
    }, true);

    // Global click capture for Send buttons
    document.addEventListener('click', (e) => {
      const target = e.target.closest('button, [role="button"]');
      if (!target) return;

      const aria = (target.getAttribute('aria-label') || '').toLowerCase();
      const testid = (target.getAttribute('data-testid') || '').toLowerCase();
      
      if (
        aria.includes('send') || 
        aria.includes('submit') || 
        testid.includes('send') ||
        target.querySelector('svg') && (aria.includes('prompt') || aria.includes('message'))
      ) {
        handleSubmission();
      }
    }, true);
  },

  /**
   * Lightweight, debounced scanner for platform rate-limit and error banners
   * Never calls document.body.innerText to prevent layout thrashing and anti-bot flags
   */
  _setupWarningScanner() {
    const warningKeywords = [
      "you've reached",
      "limit reached",
      "rate limit",
      "try again in",
      "messages remaining",
      "usage cap",
      "temporarily unavailable",
      "too many requests",
      "resets at",
      "quota exceeded"
    ];

    const alertSelectors = [
      '[role="alert"]',
      '[data-testid*="error"]',
      'div[class*="banner"]',
      'div[class*="warning"]',
      'div[class*="error"]',
      '.text-token-text-error'
    ];

    let debounceTimer = null;

    const checkAlertElements = () => {
      let matched = false;
      const candidates = document.querySelectorAll(alertSelectors.join(','));

      for (const el of candidates) {
        // Skip hidden or empty elements
        if (!el || el.offsetParent === null) continue;
        const text = (el.textContent || '').toLowerCase();
        for (const kw of warningKeywords) {
          if (text.includes(kw)) {
            matched = true;
            break;
          }
        }
        if (matched) break;
      }

      if (matched !== this.hasWarningBanner) {
        this.hasWarningBanner = matched;
        this._notifyListeners();
      }
    };

    // Low-frequency, debounced observer that ignores streaming character changes
    const observer = new MutationObserver(() => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(checkAlertElements, 1500);
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    // Initial check
    setTimeout(checkAlertElements, 2000);
  },

  _notifyListeners() {
    const state = this.getState();
    this.listeners.forEach(cb => {
      try { cb(state); } catch (e) { console.error(e); }
    });
  }
};

if (typeof window !== 'undefined') {
  window.ContextTracker = ContextTracker;
}
