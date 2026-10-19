# Changelog

All notable changes are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/) (see `spec/12-product-and-distribution.md` §7).

**Nothing has been released yet.** The sections below under *Planned* describe what each release will
contain according to the specification; they become real entries (with dates) only when the release is
cut with `RELEASING.md`. Do not tag or publish a version whose items aren't implemented.

## [Unreleased]

### Added
- Specification set `spec/00`–`spec/14`, user guides in `docs/`, `inspo/` reference project.
- `CHANGELOG.md`, `RELEASING.md`.

### Changed
- Superseded Playwright-era README/docs moved to `archive/playwright-gemini/`.

---

## Planned: [1.0.0]

OpenAI-compatible API for ChatGPT, Claude and Gemini through your own browser session.

- Extension for Chrome and Firefox (Manifest V3), provider configs as data with hot overrides.
- Bridge (Python, one dependency) as `uv` package and as standalone binaries (Linux, macOS, Windows).
- `/v1/chat/completions` (streaming + non-streaming), `/v1/models`; `sk-w2a-…` API keys with scopes,
  rate limits, rotation.
- Conversation mapping, tab pool, health checks, support bundle, `doctor`, service install.
- Security: loopback only, Origin/Host validation, pairing token.

Exit criteria: `spec/12` §11 (Definition of done for 1.0).

## Planned: [2.0.0]

The MCP release. **`/v1` API unchanged and backward compatible; protocol major remains 1** (new
capabilities only). "2.0.0" is a product-level decision (headline feature), not an API break.

### Added
- **MCP server** (stdio via `web2api-bridge mcp`, Streamable HTTP at `/mcp`): tools `chat`,
  `web_search`, `deep_research`, `task_status`, `task_reply`, `task_cancel`, `list_tasks`, `quick`,
  `commit_message`, `pr_description`, `summarize`, `generate_docs`, `list_providers`; prompts
  (`/commit`, `/pr`, `/readme`, `/docs`, `/research`, `/second-opinion`, `/search`); resources.
- **Deep Research** as long-running tasks (plan review, clarifying questions, progress, resume after
  restart), with daily caps, de-duplication and an agent-loop breaker.
- **Built-in web search mode** with extracted sources (`web2api.mode: "search"`, `web_search` tool).
- **Utility lane**: a fast, near-free model (Flash-Lite via Gemini/AI Studio, with fallbacks) for chores;
  model name `utility` in the OpenAI API too.
- **CLI companions**: `commit`, `git-hook install` (prepare-commit-msg), `docs`, `research`, `ask`,
  `mcp install` for Claude Code / Claude Desktop / Cursor / VS Code / Codex CLI / Gemini CLI / Windsurf.
- Secret scanner for everything sent to providers by the dev tools.
- Tab-pool lanes, model-variant selection, step DSL for provider modes, `tasks` key scope.

Exit criteria: `spec/10` Phase 10 acceptance criteria.

