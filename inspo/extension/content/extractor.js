/**
 * PromptRelay - Resilient DOM Extractor
 * Multi-tier waterfall extraction that survives frontend redesigns
 */

const ContextExtractor = {
  /**
   * Finds the active prompt input element using multi-tier fallback
   * @returns {HTMLElement | null}
   */
  findInputElement() {
    const platform = window.ContextDetector ? window.ContextDetector.getPlatform() : 'unknown';

    // Tier 1: Platform-specific primary selectors
    const tier1Selectors = {
      chatgpt: [
        '#prompt-textarea',
        'textarea[data-id="root"]',
        'div[id="prompt-textarea"][contenteditable="true"]',
        'div[contenteditable="true"][data-placeholder]'
      ],
      claude: [
        'div[contenteditable="true"].ProseMirror',
        'fieldset div[contenteditable="true"]',
        'div[data-testid="chat-input"] [contenteditable="true"]'
      ],
      gemini: [
        'rich-textarea div[contenteditable="true"]',
        'div.ql-editor[contenteditable="true"]',
        'div[role="textbox"][contenteditable="true"]'
      ]
    };

    if (tier1Selectors[platform]) {
      for (const selector of tier1Selectors[platform]) {
        const el = document.querySelector(selector);
        if (el && this._isElementVisible(el)) {
          return el;
        }
      }
    }

    // Tier 2: Semantic HTML5 & ARIA fallbacks (works across any site)
    const tier2Selectors = [
      'div[role="textbox"][contenteditable="true"]',
      'div[contenteditable="true"]',
      'textarea[placeholder*="message" i]',
      'textarea[placeholder*="prompt" i]',
      'textarea[placeholder*="ask" i]',
      'textarea',
      'input[type="text"][placeholder*="message" i]'
    ];

    for (const selector of tier2Selectors) {
      const candidates = document.querySelectorAll(selector);
      for (const el of candidates) {
        if (this._isElementVisible(el)) {
          return el;
        }
      }
    }

    return null;
  },

  /**
   * Polls until the active input element mounts on the page
   * Survives cold navigations, auth token verification, and Cloudflare challenges
   * @param {number} retries - Number of polling attempts
   * @param {number} delayMs - Milliseconds between checks
   * @returns {Promise<HTMLElement | null>}
   */
  async waitForInputElement(retries = 30, delayMs = 250) {
    for (let i = 0; i < retries; i++) {
      const el = this.findInputElement();
      if (el && (el.offsetParent !== null || el.isContentEditable)) {
        return el;
      }
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
    return null;
  },

  /**
   * Finds the last assistant message element
   * @returns {HTMLElement | null}
   */
  findLatestAssistantMessage() {
    const platform = window.ContextDetector ? window.ContextDetector.getPlatform() : 'unknown';

    // Tier 1: Platform-specific assistant role tags
    if (platform === 'chatgpt') {
      const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
      if (messages.length > 0) {
        return messages[messages.length - 1];
      }
      const articles = document.querySelectorAll('article');
      if (articles.length > 0) {
        // Find last article that contains markdown / assistant styling
        for (let i = articles.length - 1; i >= 0; i--) {
          if (articles[i].querySelector('.markdown') || articles[i].textContent.length > 50) {
            return articles[i];
          }
        }
      }
    }

    if (platform === 'claude') {
      const messages = document.querySelectorAll('[data-is-streaming], .font-claude-message, [class*="message-content"]');
      if (messages.length > 0) {
        return messages[messages.length - 1];
      }
      const genericMessages = document.querySelectorAll('[class*="prose"]');
      if (genericMessages.length > 0) {
        return genericMessages[genericMessages.length - 1];
      }
    }

    if (platform === 'gemini') {
      const responses = document.querySelectorAll('model-response, .message-content, .response-container');
      if (responses.length > 0) {
        return responses[responses.length - 1];
      }
    }

    // Tier 2: Generic Structural Traversal (find last markdown / prose container)
    const proseContainers = document.querySelectorAll('.markdown, [class*="markdown"], [class*="prose"]');
    if (proseContainers.length > 0) {
      return proseContainers[proseContainers.length - 1];
    }

    return null;
  },

  /**
   * Extracts clean text content from the latest assistant message
   * @returns {string}
   */
  extractLatestResponseText() {
    // Check if user currently has manual selection
    const selection = window.getSelection().toString().trim();
    if (selection && selection.length > 40) {
      return selection;
    }

    const messageEl = this.findLatestAssistantMessage();
    if (!messageEl) {
      return '';
    }

    // Clone node so we can clean up UI buttons (copy buttons, thumbs up/down, etc.)
    const clone = messageEl.cloneNode(true);
    const ignoreSelectors = [
      'button',
      '[role="button"]',
      '.sr-only',
      'svg',
      '[class*="feedback"]',
      '[class*="actions"]',
      '[class*="copy"]'
    ];
    ignoreSelectors.forEach(sel => {
      clone.querySelectorAll(sel).forEach(el => el.remove());
    });

    return clone.innerText.trim();
  },

  /**
   * Helper to verify element is visible and interactive
   */
  _isElementVisible(el) {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    return (
      style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      style.opacity !== '0' &&
      el.offsetWidth > 0 &&
      el.offsetHeight > 0
    );
  }
};

if (typeof window !== 'undefined') {
  window.ContextExtractor = ContextExtractor;
}
