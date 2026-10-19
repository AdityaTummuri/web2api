/**
 * PromptRelay - Storage Utilities
 * 100% on-device wrapper for chrome.storage.local
 */

const DEFAULT_SETTINGS = {
  // Usage tracking limits before triggering warning
  thresholds: {
    chatgpt: 30, // Default safe estimate for 3h window
    claude: 20,  // Default safe estimate for 5h window
    gemini: 40
  },
  // Window duration in hours for rolling limits
  windowHours: {
    chatgpt: 3,
    claude: 5,
    gemini: 4
  },
  // Auto-warn when reaching X% of threshold
  warningPercentage: 80,
  // Preferred default teleport destination
  preferredTarget: 'claude',
  // Floating HUD visibility
  hudEnabled: true
};

const ContextStorage = {
  /**
   * Retrieves user settings with fallback defaults
   */
  async getSettings() {
    return new Promise((resolve) => {
      chrome.storage.local.get(['cr_settings'], (result) => {
        resolve({ ...DEFAULT_SETTINGS, ...(result.cr_settings || {}) });
      });
    });
  },

  /**
   * Updates user settings
   */
  async saveSettings(newSettings) {
    return new Promise((resolve) => {
      chrome.storage.local.set({ cr_settings: newSettings }, () => {
        resolve(newSettings);
      });
    });
  },

  /**
   * Logs a user-sent prompt timestamp for a specific platform
   */
  async logPrompt(platform) {
    return new Promise((resolve) => {
      chrome.storage.local.get(['cr_prompts'], (result) => {
        const prompts = result.cr_prompts || [];
        const entry = {
          id: 'p_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4),
          platform,
          timestamp: Date.now()
        };
        // Keep last 100 prompts max to prevent unconstrained storage growth
        const updated = [...prompts.slice(-99), entry];
        chrome.storage.local.set({ cr_prompts: updated }, () => {
          resolve(entry);
        });
      });
    });
  },

  /**
   * Calculates how many prompts have been sent within the rolling window
   */
  async getRecentPromptCount(platform, windowHours = 3) {
    return new Promise((resolve) => {
      chrome.storage.local.get(['cr_prompts'], (result) => {
        const prompts = result.cr_prompts || [];
        const cutoff = Date.now() - (windowHours * 60 * 60 * 1000);
        const count = prompts.filter(p => p.platform === platform && p.timestamp >= cutoff).length;
        resolve(count);
      });
    });
  },

  /**
   * Saves a generated handover capsule locally
   */
  async saveHandoverCapsule(capsule) {
    return new Promise((resolve) => {
      chrome.storage.local.get(['cr_capsules'], (result) => {
        const capsules = result.cr_capsules || [];
        const newEntry = {
          id: 'cap_' + Date.now(),
          timestamp: Date.now(),
          sourcePlatform: capsule.sourcePlatform,
          title: capsule.title || `Handover from ${capsule.sourcePlatform}`,
          content: capsule.content
        };
        // Keep the 10 most recent capsules for ultra-lean storage footprint
        const updated = [newEntry, ...capsules.slice(0, 9)];
        chrome.storage.local.set({ 
          cr_capsules: updated,
          cr_latest_capsule: newEntry 
        }, () => {
          resolve(newEntry);
        });
      });
    });
  },

  /**
   * Retrieves all saved handover capsules
   */
  async getHandoverCapsules() {
    return new Promise((resolve) => {
      chrome.storage.local.get(['cr_capsules'], (result) => {
        resolve(result.cr_capsules || []);
      });
    });
  },

  /**
   * Retrieves the most recent handover capsule
   */
  async getLatestCapsule() {
    return new Promise((resolve) => {
      chrome.storage.local.get(['cr_latest_capsule'], (result) => {
        resolve(result.cr_latest_capsule || null);
      });
    });
  },

  /**
   * Clears saved handover capsules
   */
  async clearCapsules() {
    return new Promise((resolve) => {
      chrome.storage.local.remove(['cr_capsules', 'cr_latest_capsule'], () => {
        resolve(true);
      });
    });
  },

  /**
   * Resets session prompt counters for a platform
   */
  async resetPromptCounter(platform) {
    return new Promise((resolve) => {
      chrome.storage.local.get(['cr_prompts'], (result) => {
        const prompts = result.cr_prompts || [];
        const filtered = prompts.filter(p => p.platform !== platform);
        chrome.storage.local.set({ cr_prompts: filtered }, () => {
          resolve(true);
        });
      });
    });
  }
};

// Export for ES modules and standard script inclusion
if (typeof window !== 'undefined') {
  window.ContextStorage = ContextStorage;
}
