/**
 * Web2API Pro Parser & Transformer Module
 * Handles deep DOM cleaning, code-block preservation, markdown transformation,
 * regex-based structured JSON extraction, and tiny ONNX/LLM normalizer interfaces.
 */

const Web2APIParser = {
  /**
   * Convert an HTML DOM element (from Gemini/ChatGPT/Claude message container)
   * into clean, pristine Markdown with perfect code blocks and tables.
   */
  domToMarkdown(rootElement) {
    if (!rootElement) return "";

    // Clone element to avoid mutating live DOM
    const clone = rootElement.cloneNode(true);

    // Remove noise elements: action buttons, thumbs up/down, copy buttons, etc.
    const noiseSelectors = [
      ".response-footer",
      ".actions-container",
      "button",
      ".copy-button",
      ".source-container",
      ".citation-container",
      "mat-icon",
      ".draft-container",
      ".user-feedback",
      "[aria-label*='Copy']",
      "[aria-label*='draft']",
      "[aria-label*='Listen']",
      "[aria-label*='Share']",
      "[aria-label*='More']"
    ];

    noiseSelectors.forEach(sel => {
      clone.querySelectorAll(sel).forEach(el => el.remove());
    });

    return this._parseNode(clone).trim();
  },

  /**
   * Recursive DOM node parser
   */
  _parseNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.nodeValue;
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }

    const tag = node.tagName.toLowerCase();

    // 1. Code blocks (<pre><code> or <pre>)
    if (tag === "pre") {
      const codeEl = node.querySelector("code") || node;
      let language = "";

      // Detect language from class names (e.g. language-python, lang-js)
      const className = (codeEl.className || "") + " " + (node.className || "");
      const langMatch = className.match(/(?:language|lang)-([a-zA-Z0-9_-]+)/i);
      if (langMatch) {
        language = langMatch[1].toLowerCase();
      } else {
        // Check data attributes or parent labels
        const langAttr = codeEl.getAttribute("data-language") || node.getAttribute("data-language");
        if (langAttr) language = langAttr.toLowerCase();
      }

      // Extract raw code text without stripping internal indentation
      let codeText = codeEl.innerText || codeEl.textContent || "";
      // Remove trailing whitespace and newlines
      codeText = codeText.replace(/\r\n/g, "\n").replace(/\n+$/, "");

      return `\n\n\`\`\`${language}\n${codeText}\n\`\`\`\n\n`;
    }

    // 2. Inline code
    if (tag === "code" && node.parentElement?.tagName.toLowerCase() !== "pre") {
      const text = node.textContent || "";
      return `\`${text}\``;
    }

    // 3. Headings
    if (/^h[1-6]$/.test(tag)) {
      const level = parseInt(tag[1], 10);
      const prefix = "#".repeat(level);
      const content = this._parseChildren(node).trim();
      return `\n\n${prefix} ${content}\n\n`;
    }

    // 4. Paragraphs and divs
    if (tag === "p") {
      const content = this._parseChildren(node).trim();
      return `\n\n${content}\n\n`;
    }

    // 5. Blockquotes
    if (tag === "blockquote") {
      const content = this._parseChildren(node).trim();
      const quoted = content.split("\n").map(line => `> ${line}`).join("\n");
      return `\n\n${quoted}\n\n`;
    }

    // 6. Lists
    if (tag === "ul") {
      const items = Array.from(node.children)
        .filter(c => c.tagName.toLowerCase() === "li")
        .map(li => `* ${this._parseChildren(li).trim()}`)
        .join("\n");
      return `\n\n${items}\n\n`;
    }

    if (tag === "ol") {
      let counter = 1;
      const items = Array.from(node.children)
        .filter(c => c.tagName.toLowerCase() === "li")
        .map(li => `${counter++}. ${this._parseChildren(li).trim()}`)
        .join("\n");
      return `\n\n${items}\n\n`;
    }

    if (tag === "li") {
      return this._parseChildren(node);
    }

    // 7. Bold & Italic
    if (tag === "strong" || tag === "b") {
      return `**${this._parseChildren(node)}**`;
    }
    if (tag === "em" || tag === "i") {
      return `*${this._parseChildren(node)}*`;
    }

    // 8. Tables
    if (tag === "table") {
      return this._parseTable(node);
    }

    // 9. Links
    if (tag === "a") {
      const href = node.getAttribute("href") || "#";
      const title = this._parseChildren(node).trim() || href;
      return `[${title}](${href})`;
    }

    // 10. Horizontal rule
    if (tag === "hr") {
      return "\n\n---\n\n";
    }

    // Default container parsing
    return this._parseChildren(node);
  },

  _parseChildren(node) {
    let result = "";
    node.childNodes.forEach(child => {
      result += this._parseNode(child);
    });
    return result;
  },

  _parseTable(tableNode) {
    const rows = Array.from(tableNode.querySelectorAll("tr"));
    if (rows.length === 0) return "";

    let md = "\n\n";
    rows.forEach((row, rowIndex) => {
      const cells = Array.from(row.querySelectorAll("th, td"));
      const cellTexts = cells.map(c => this._parseChildren(c).trim().replace(/\|/g, "\\|"));
      md += `| ${cellTexts.join(" | ")} |\n`;

      // Insert delimiter row after header
      if (rowIndex === 0) {
        const delimiters = cells.map(() => "---");
        md += `| ${delimiters.join(" | ")} |\n`;
      }
    });
    md += "\n";
    return md;
  },

  /**
   * Extract all fenced code blocks from markdown text.
   * Returns array of { language, code, index }
   */
  extractCodeBlocks(markdownText) {
    const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
    const blocks = [];
    let match;
    let index = 0;

    while ((match = codeBlockRegex.exec(markdownText)) !== null) {
      blocks.push({
        index: index++,
        language: match[1].toLowerCase() || "text",
        code: match[2].trim()
      });
    }

    return blocks;
  },

  /**
   * Regex-based structured JSON extractor.
   * Finds JSON blocks either fenced in ```json or bare { ... } / [ ... ].
   */
  extractStructuredJson(rawText) {
    if (!rawText) return null;

    // 1. Try markdown fenced JSON
    const fencedMatch = rawText.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
    if (fencedMatch) {
      try {
        return JSON.parse(fencedMatch[1].trim());
      } catch (e) {
        // Not valid JSON in fence, fall through
      }
    }

    // 2. Try raw outermost JSON object
    const objMatch = rawText.match(/(\{[\s\S]*\})/);
    if (objMatch) {
      try {
        return JSON.parse(objMatch[1].trim());
      } catch (e) {
        // Fall through
      }
    }

    // 3. Try raw outermost JSON array
    const arrMatch = rawText.match(/(\[[\s\S]*\])/);
    if (arrMatch) {
      try {
        return JSON.parse(arrMatch[1].trim());
      } catch (e) {
        // Fall through
      }
    }

    return null;
  },

  /**
   * Detect and extract Tool Calls / Function Calls from text.
   * Supports XML <tool_call>, function_name{...}, or call:name{...}
   */
  extractToolCalls(rawText) {
    const toolCalls = [];

    // Pattern A: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
    const xmlRegex = /<tool_call>([\s\S]*?)<\/tool_call>/gi;
    let match;
    while ((match = xmlRegex.exec(rawText)) !== null) {
      try {
        const parsed = JSON.parse(match[1].trim());
        toolCalls.push(parsed);
      } catch (e) {}
    }

    // Pattern B: call:funcName({...})
    const callRegex = /(?:call|tool):([a-zA-Z0-9_-]+)\s*\(([\s\S]*?)\)/gi;
    while ((match = callRegex.exec(rawText)) !== null) {
      try {
        const args = JSON.parse(match[2].trim());
        toolCalls.push({ name: match[1], arguments: args });
      } catch (e) {
        toolCalls.push({ name: match[1], rawArguments: match[2].trim() });
      }
    }

    return toolCalls;
  },

  /**
   * TinyLLM / ONNX Normalizer Interface
   * Uses regex rules or an optional lightweight ONNX model to normalize
   * conversational chat responses into strict API schemas.
   */
  normalizeToApiResponse(rawText, options = {}) {
    const markdown = rawText.replace(/\r\n/g, "\n").trim();
    const codeBlocks = this.extractCodeBlocks(markdown);
    const structuredJson = this.extractStructuredJson(markdown);
    const toolCalls = this.extractToolCalls(markdown);

    const modelName = options.model || "gemini-web-pro";
    const reqId = options.id || `chatcmpl-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;

    // Build standard OpenAI-compatible chat completion response
    const response = {
      id: reqId,
      object: "chat.completion",
      created: Math.floor(Date.now() / 1000),
      model: modelName,
      choices: [
        {
          index: 0,
          message: {
            role: "assistant",
            content: markdown
          },
          finish_reason: "stop"
        }
      ],
      usage: {
        prompt_tokens: Math.round((options.prompt?.length || 0) / 4),
        completion_tokens: Math.round(markdown.length / 4),
        total_tokens: Math.round(((options.prompt?.length || 0) + markdown.length) / 4)
      },
      // Pro-level extensions
      extracted: {
        code_blocks: codeBlocks,
        structured_data: structuredJson,
        tool_calls: toolCalls.length > 0 ? toolCalls : null
      }
    };

    return response;
  }
};

// Export for WebExtension environment (global or module)
if (typeof window !== "undefined") {
  window.Web2APIParser = Web2APIParser;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = Web2APIParser;
}
