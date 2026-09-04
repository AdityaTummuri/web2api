const test = require("node:test");
const assert = require("node:assert/strict");
const Web2APIParser = require("./parser.js");

test("extractCodeBlocks - parses fenced code blocks with language", () => {
  const md = `
Here is the solution:

\`\`\`python
def fib(n):
    return n if n <= 1 else fib(n-1) + fib(n-2)
\`\`\`

And in Rust:

\`\`\`rust
fn fib(n: u32) -> u32 {
    match n {
        0 | 1 => n,
        _ => fib(n - 1) + fib(n - 2),
    }
}
\`\`\`
`;

  const blocks = Web2APIParser.extractCodeBlocks(md);
  assert.equal(blocks.length, 2);
  assert.equal(blocks[0].language, "python");
  assert.ok(blocks[0].code.includes("def fib(n):"));
  assert.equal(blocks[1].language, "rust");
  assert.ok(blocks[1].code.includes("fn fib(n: u32)"));
});

test("extractStructuredJson - parses markdown fenced JSON", () => {
  const text = `
Sure! Here is the structured result:

\`\`\`json
{
  "status": "success",
  "items": [1, 2, 3],
  "verified": true
}
\`\`\`
`;

  const data = Web2APIParser.extractStructuredJson(text);
  assert.ok(data);
  assert.equal(data.status, "success");
  assert.deepEqual(data.items, [1, 2, 3]);
  assert.equal(data.verified, true);
});

test("extractToolCalls - parses XML and function style tool calls", () => {
  const text = `
I will inspect the filesystem.
<tool_call>
{"tool": "read_file", "parameters": {"path": "bridge_server.py"}}
</tool_call>
`;

  const calls = Web2APIParser.extractToolCalls(text);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].tool, "read_file");
  assert.equal(calls[0].parameters.path, "bridge_server.py");
});

test("normalizeToApiResponse - produces standard OpenAI payload", () => {
  const text = "Hello from Gemini!\n\n```javascript\nconsole.log('hi');\n```";
  const res = Web2APIParser.normalizeToApiResponse(text, {
    prompt: "Say hi in js",
    model: "gemini-pro"
  });

  assert.equal(res.object, "chat.completion");
  assert.equal(res.model, "gemini-pro");
  assert.equal(res.choices[0].message.role, "assistant");
  assert.ok(res.choices[0].message.content.includes("console.log('hi')"));
  assert.equal(res.extracted.code_blocks.length, 1);
  assert.equal(res.extracted.code_blocks[0].language, "javascript");
});
