/**
 * PromptRelay - Platform Detector
 * Identifies the current AI chat environment and active model metadata
 */

const ContextDetector = {
  /**
   * Identifies current platform from host and location
   * @returns {'chatgpt' | 'claude' | 'gemini' | 'unknown'}
   */
  getPlatform() {
    const host = window.location.hostname;
    if (host.includes('chatgpt.com') || host.includes('openai.com')) {
      return 'chatgpt';
    }
    if (host.includes('claude.ai')) {
      return 'claude';
    }
    if (host.includes('gemini.google.com')) {
      return 'gemini';
    }
    return 'unknown';
  },

  /**
   * Returns human-readable platform name
   */
  getPlatformName() {
    const p = this.getPlatform();
    switch (p) {
      case 'chatgpt': return 'ChatGPT';
      case 'claude': return 'Claude';
      case 'gemini': return 'Gemini';
      default: return 'AI Assistant';
    }
  },

  /**
   * Attempts to extract the conversation title from document or header
   */
  getConversationTitle() {
    // Platform-specific title extractions
    const p = this.getPlatform();
    
    if (p === 'chatgpt') {
      const titleElem = document.querySelector('title');
      if (titleElem && titleElem.textContent && !titleElem.textContent.includes('ChatGPT')) {
        return titleElem.textContent.trim();
      }
      const navActive = document.querySelector('nav a[class*="active"], nav li[class*="active"]');
      if (navActive && navActive.textContent) {
        return navActive.textContent.trim();
      }
    }

    if (p === 'claude') {
      const headerTitle = document.querySelector('[data-testid="chat-title"], h1, button[aria-label*="conversation"]');
      if (headerTitle && headerTitle.textContent) {
        return headerTitle.textContent.trim();
      }
    }

    if (p === 'gemini') {
      const geminiTitle = document.querySelector('.conversation-title, h1');
      if (geminiTitle && geminiTitle.textContent) {
        return geminiTitle.textContent.trim();
      }
    }

    // Fallback to page title or timestamp
    return document.title ? document.title.replace(/(ChatGPT|Claude|Gemini)/i, '').trim() || 'Active Session' : 'Active Session';
  }
};

if (typeof window !== 'undefined') {
  window.ContextDetector = ContextDetector;
}
