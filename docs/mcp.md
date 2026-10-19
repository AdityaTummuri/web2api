# Web2API as an MCP server (v2.0.0)

> **Planned for release 2.0.0** — target-state guide (see README status note). Design:
> `spec/14-mcp-server-v2.md`. MCP client configuration formats change; if a snippet below doesn't match
> your client's current docs, trust the client docs and use the same command/URL.

MCP ([Model Context Protocol](https://modelcontextprotocol.io)) lets coding assistants and chat apps use
external tools. With Web2API's MCP server, your assistant can:

* **chat** with Claude / ChatGPT / Gemini for a second opinion,
* **search the web** with a model's built-in search and get cited answers,
* run **Deep Research** (multi-source cited reports — the browser versions have it, the cheap APIs don't),
* hand chores — **commit messages, PR descriptions, summaries, README and docs** — to a fast, effectively
  free model so your main assistant doesn't spend its own tokens on them.

Everything runs through *your* logged-in browser via the bridge ([quick start](quickstart.md)).

## Set up in three commands

```bash
web2api-bridge service install                      # keep the bridge running (once)
web2api-bridge mcp install --client claude-code --write
# restart/refresh your client
```
`mcp install` creates a narrow key named `mcp` (chat + tasks, no admin), stores it where the MCP process
can read it, and prints or writes the client configuration. Clients: `claude-code`, `claude-desktop`,
`cursor`, `vscode`, `codex`, `gemini-cli`, `windsurf`, `generic`. Without `--write` it only prints the
snippet. With `--write` it edits the client's config after making a timestamped backup.

Check it: `web2api-bridge doctor` has an MCP section (key present, `/mcp` reachable, tools, which model
the utility lane uses, which providers support search / Deep Research on *your* account).

## Manual configuration

Use the full path to the executable if it isn't on your `PATH` (`which web2api-bridge`).

**Claude Code**
```bash
claude mcp add web2api -- web2api-bridge mcp
# or over HTTP:
claude mcp add --transport http web2api http://127.0.0.1:8787/mcp --header "Authorization: Bearer sk-w2a-…"
```

**Claude Desktop** (`claude_desktop_config.json`) and **Cursor** (`~/.cursor/mcp.json`)
```json
{ "mcpServers": { "web2api": { "command": "web2api-bridge", "args": ["mcp"] } } }
```

**VS Code** (`.vscode/mcp.json`)
```json
{ "servers": { "web2api": { "type": "stdio", "command": "web2api-bridge", "args": ["mcp"] } } }
```

**Codex CLI** (`~/.codex/config.toml`)
```toml
[mcp_servers.web2api]
command = "web2api-bridge"
args = ["mcp"]
```

**Gemini CLI** (`~/.gemini/settings.json`)
```json
{ "mcpServers": { "web2api": { "command": "web2api-bridge", "args": ["mcp"] } } }
```
The stdio server finds its key from `--key`, then `WEB2API_API_KEY`, then the `mcp` key file created by
`mcp install`. If the bridge isn't running, the server still starts and every tool answers
"Web2API bridge isn't running — start it with `web2api-bridge`" (add `--spawn-bridge` to have it start
one for you).

Show fewer tools (helps your assistant choose well): `args = ["mcp", "--toolsets", "core,dev"]`.
Toolsets: `core` (chat, web_search, list_providers), `research` (deep research + task tools), `dev`
(quick, commit_message, pr_description, summarize, generate_docs).

## The tools

| Tool | Use it for |
|---|---|
| `chat` | A conversation or second opinion with a web AI. Pass the returned `conversation` id to continue; `search: true` for current info. |
| `web_search` | A question that needs fresh facts; returns a short answer **with source links**. |
| `deep_research` | A thorough multi-source report. Returns a `task_id` immediately (takes 5–30 min). |
| `task_status` | Check a task; `wait_seconds` (up to 50) waits efficiently; returns the report when done. |
| `task_reply` | Approve a research plan, answer the provider's clarifying question, or resume an interrupted task. |
| `task_cancel`, `list_tasks` | Stop a task / list your tasks. |
| `quick` | Small chores for the fast free model: rephrase, classify, extract, tiny questions. |
| `commit_message` | Conventional-Commits message from `git diff --staged`. |
| `pr_description` | Title + body from a diff or commit list. |
| `summarize` | Summarise long text (handles very long input). |
| `generate_docs` | README, API reference, architecture overview, docstrings, changelog… from file contents. |
| `list_providers` | What's available now and what each can do. |

You normally don't call these yourself — you ask your assistant ("search the web for…", "write a commit
message for my staged changes", "do deep research on…") and it picks the tool. Details:
[Deep Research and search](research-and-search.md), [Developer chores](dev-tools.md).

### Slash-command shortcuts (MCP prompts)
Clients that support MCP prompts show: `commit`, `pr`, `readme`, `docs`, `research`, `second-opinion`,
`search`. In Claude Code they appear as `/mcp__web2api__commit` etc.

## Good to know
* **It uses your browser:** keep Chrome/Firefox running with the extension; Deep Research and heavy
  use make a worker window busy for a long time (the extension keeps separate tabs for chores, chat and
  research so one doesn't block the others).
* **Privacy:** code you send to the dev tools goes to the chosen chat provider's website. A built-in
  secret scanner redacts keys/tokens/passwords first (`on_secrets: redact` by default; set `refuse` to
  block instead). Your conversations appear in provider history (chores use temporary chats where the
  site supports them).
* **Untrusted content:** web search results and research reports come from the open web. They're returned
  as data; your assistant should not follow instructions found inside them.
* **Limits protect your accounts:** Deep Research is capped per day (default 5 per provider), duplicates
  are merged, and an assistant that starts runaway research is stopped. Change in `config.toml` under
  `[mcp.research]`.
* **Terms of service:** automating consumer chat sites may violate their terms (see README warning).

## Configuration (`config.toml`)

```toml
[mcp]
toolsets = ["core", "research", "dev"]
chat_provider_order     = ["claude", "chatgpt", "gemini"]
search_provider_order   = ["perplexity", "gemini", "chatgpt", "claude"]
research_provider_order = ["gemini", "chatgpt", "claude", "perplexity"]
[mcp.utility]                       # the fast free model used for chores
provider = "gemini"                 # or "aistudio" — whichever offers Flash-Lite on your account
variant  = "flash-lite"
fallback = ["chatgpt/default", "claude/default"]
[mcp.research]
max_per_day = 5
confirm = "elicit"                  # ask you (if your client supports it) before starting research
```
Full list and meanings: `spec/14-mcp-server-v2.md` §4.1.

## Troubleshooting
* Tools missing → restart the client; run `web2api-bridge doctor`.
* "Bridge isn't running" → `web2api-bridge service install` (or run `web2api-bridge`).
* "utility_unavailable" → the fast model's site is logged out / rate-limited and no fallback worked;
  see the message and [Troubleshooting](troubleshooting.md).
* Deep Research says "not available" → your account/plan on that site may not include it; try another
  provider (`list_providers` shows what is available).
