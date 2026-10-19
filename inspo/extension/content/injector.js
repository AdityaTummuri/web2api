/**
 * PromptRelay - Safe Text Injector
 * Emulates native human clipboard pasting (execCommand + InputEvent)
 * Strictly stages text for user review - NEVER auto-submits
 */

const ContextInjector = {
  /**
   * Stages text into the platform's active input box
   * @param {string} text - The content to insert
   * @param {HTMLElement | null} targetEl - Optional already-resolved target element
   * @returns {boolean} Success status
   */
  injectText(text, targetEl = null) {
    if (!text) return false;

    const inputEl = targetEl || (window.ContextExtractor ? window.ContextExtractor.findInputElement() : null);
    if (!inputEl) {
      console.warn('[PromptRelay] Could not locate input box for injection.');
      return false;
    }

    try {
      // 1. Focus the input element
      inputEl.focus();
      inputEl.scrollIntoView({ behavior: 'smooth', block: 'center' });

      // 2. Handle based on element type
      if (inputEl.tagName === 'TEXTAREA' || inputEl.tagName === 'INPUT') {
        return this._injectIntoTextarea(inputEl, text);
      } else if (inputEl.isContentEditable || inputEl.getAttribute('contenteditable') === 'true') {
        return this._injectIntoContentEditable(inputEl, text);
      }

      return false;
    } catch (err) {
      console.error('[PromptRelay] Insertion failed:', err);
      return false;
    }
  },

  /**
   * Safe insertion into standard textarea
   */
  _injectIntoTextarea(textarea, text) {
    // Select all existing content or place at end
    textarea.focus();
    
    // Try native execCommand first (safest and notifies React state)
    const success = document.execCommand('insertText', false, text);
    
    if (!success) {
      // Fallback: standard value setter + native event dispatch
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const val = textarea.value;
      textarea.value = val.substring(0, start) + text + val.substring(end);
      textarea.selectionStart = textarea.selectionEnd = start + text.length;

      // Dispatch React/framework friendly input events
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
      textarea.dispatchEvent(new Event('change', { bubbles: true }));
    }

    this._pulseInput(textarea);
    return true;
  },

  /**
   * Safe insertion into rich-text contenteditable (ProseMirror, Lexical, etc.)
   */
  _injectIntoContentEditable(editable, text) {
    editable.focus();

    // 1. Synthetic ClipboardEvent: ProseMirror (Claude) uses clipboardTextParser
    // which cleanly slices multiline markdown into paragraphs and updates internal state
    try {
      const dt = new DataTransfer();
      dt.setData('text/plain', text);
      const pasteEvent = new ClipboardEvent('paste', {
        clipboardData: dt,
        bubbles: true,
        cancelable: true
      });
      const wasPrevented = !editable.dispatchEvent(pasteEvent);
      // If ProseMirror or the editor intercepted it, or content was added
      if (wasPrevented || editable.textContent.includes(text.slice(0, 30))) {
        this._pulseInput(editable);
        return true;
      }
    } catch (e) {
      console.warn('[PromptRelay] Synthetic paste fallback:', e);
    }

    // 2. Fallback: execCommand('insertText')
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(editable);
    range.collapse(false); // Move to end
    selection.removeAllRanges();
    selection.addRange(range);

    // Primary: execCommand creates native Undo history and triggers framework listeners
    let inserted = document.execCommand('insertText', false, text);

    if (!inserted) {
      // Fallback for modern editors that intercept execCommand
      const textNode = document.createTextNode(text);
      range.insertNode(textNode);
      range.setStartAfter(textNode);
      range.setEndAfter(textNode);
      selection.removeAllRanges();
      selection.addRange(range);

      // Trigger input event
      const event = new InputEvent('input', {
        bubbles: true,
        cancelable: true,
        inputType: 'insertText',
        data: text
      });
      editable.dispatchEvent(event);
    }

    this._pulseInput(editable);
    return true;
  },

  /**
   * Visual feedback pulse to show user where text was staged
   */
  _pulseInput(el) {
    const originalOutline = el.style.outline;
    const originalTransition = el.style.transition;
    
    el.style.transition = 'outline 0.3s ease-in-out';
    el.style.outline = '2px solid #6366f1';
    
    setTimeout(() => {
      el.style.outline = originalOutline;
      el.style.transition = originalTransition;
    }, 1200);
  }
};

if (typeof window !== 'undefined') {
  window.ContextInjector = ContextInjector;
}
