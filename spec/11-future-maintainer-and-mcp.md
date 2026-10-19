# 11 — Future: the Maintainer Agent and the MCP Server

Neither is built in v1. This document exists so that v1 is built with the right **hooks**, and so the
next engineer has a design to start from. §3 lists the hooks that v1 must include.

---

## 1. The maintainer agent

### 1.1 Problem

Chat sites redesign constantly. Every change can break a selector, the completion detection, or a
stream parser. Today a human would notice failures, open DevTools, find new selectors, and ship a fix.
The maintainer automates that loop using a real (paid) LLM API, e.g. a current Claude model through
the Anthropic API.

### 1.2 Where it runs

A separate Python process (`maintainer/` package, later) that talks to the bridge's **admin API**
(`07` §9) with a dedicated `admin`-scope API key (`13`), and to the LLM provider's official API with its own API key. It never
talks to the extension directly and never touches browser cookies.

### 1.3 Loop

```
           ┌────────────────────────────────────────────────────────────────────────┐
           │ 1. DETECT                                                              │
           │    poll GET /web2api/health/reports and /web2api/providers             │
           │    triggers: provider status unhealthy/degraded; SELECTOR_NOT_FOUND,   │
           │    SUBMIT_FAILED, NO_RESPONSE spikes; net_dom_divergence warnings;     │
           │    scheduled canary (daily POST .../probe)                             │
           └──────────────┬─────────────────────────────────────────────────────────┘
                          ▼
           ┌────────────────────────────────────────────────────────────────────────┐
           │ 2. GATHER                                                              │
           │    effective config (GET /web2api/config/{id}), failing keys + tiers,  │
           │    fresh redacted DOM snapshot (POST .../snapshot), last known-good    │
           │    fixture from git, RECON.md, selector authoring rules (05 §2.2)      │
           └──────────────┬─────────────────────────────────────────────────────────┘
                          ▼
           ┌────────────────────────────────────────────────────────────────────────┐
           │ 3. PROPOSE (LLM)                                                       │
           │    input: the above; output: a JSON Merge Patch override (05 §2.4)     │
           │    with a reason, using only allowed fields; structured output         │
           └──────────────┬─────────────────────────────────────────────────────────┘
                          ▼
           ┌────────────────────────────────────────────────────────────────────────┐
           │ 4. VALIDATE OFFLINE                                                    │
           │    schema + override rules; resolve every critical key against the new │
           │    snapshot in jsdom (same code as DOM fixture tests); type checks     │
           │    (input is textarea/contenteditable, send is a button, not matching  │
           │    destructive deny list); old fixture should ideally still pass too   │
           └──────────────┬─────────────────────────────────────────────────────────┘
                          ▼
           ┌────────────────────────────────────────────────────────────────────────┐
           │ 5. VALIDATE LIVE (dry run)                                             │
           │    HEALTH_PROBE with candidateConfig (no persistence) on an idle tab   │
           │    → all critical keys found at tier 0                                 │
           │    then one canary job ("Reply with exactly PONG") with the candidate  │
           │    applied as a temporary override; revert automatically on failure    │
           └──────────────┬─────────────────────────────────────────────────────────┘
                          ▼
           ┌────────────────────────────────────────────────────────────────────────┐
           │ 6. APPLY & REPORT                                                      │
           │    POST /web2api/config/{id}/override (source "maintainer")            │
           │    notify owner (desktop notification / log / chat message)            │
           │    open a git branch + PR folding the override into the bundled JSON,  │
           │    adding the new snapshot as a fixture, bumping configVersion         │
           └────────────────────────────────────────────────────────────────────────┘
```

**Parser breakage** (net tap): stream formats are code, not data, so the maintainer cannot hot-fix
them. Meanwhile the extension automatically falls back to DOM extraction (D5). The maintainer
requests a fresh redacted stream sample (§3 hook H4), asks the LLM for a parser patch + updated test,
runs the parser tests locally, and opens a PR for human review. It never auto-merges code.

### 1.4 Guardrails

* Only data overrides are auto-applied; code changes always go through a human-reviewed PR.
* Max one auto-applied override per provider per hour; after two failed attempts, stop and notify.
* Every override carries `source: "maintainer"` and a reason; the owner can revert from the popup.
* Snapshots sent to the LLM API are the redacted ones (`04` §9.3) — conversation text never leaves the
  machine. The maintainer must refuse to run if it receives an unredacted snapshot (check for the
  redaction marker comment).
* The LLM output is untrusted: it is parsed as JSON, validated against the schema and override rules,
  and tested before use. Never `eval`.

---

## 2. The MCP server

> **Superseded by `14-mcp-server-v2.md`** (release v2.0.0): the design below was an early sketch
> (separate package, official SDK). The shipped design is in-bridge, stdlib-only, with the tools,
> lanes and workflows defined in `14`. Keep this section only for the original motivation.

### 2.1 Purpose

Let MCP clients (Claude Code, Claude Desktop, Cursor, …) use the web chat models as tools — e.g.
"ask Gemini for a second opinion on this diff" — without each client needing OpenAI-compatible
configuration.

### 2.2 Shape

* Separate small Python package `mcp/` (stdio transport, since most MCP clients spawn local servers),
  using the official MCP Python SDK. Talks to the bridge over HTTP with a `chat`-scope API key (`13`) (read from the
  token file or an env var).
* Tools (initial set):
  | Tool | Input | Output |
  |---|---|---|
  | `web2api_ask` | `provider` (enum from `/web2api/providers`), `prompt`, `thread` (`"new"` default, or a thread URL from a previous result), `include_reasoning` | answer markdown + `thread_url` |
  | `web2api_list_providers` | — | provider ids, status, display names |
  | `web2api_health` | `provider?` | health summary |
* Resources (optional): `web2api://providers` status JSON.
* Long answers: MCP tool calls are request/response; use the bridge's non-streaming endpoint with
  generous timeouts. Report progress via MCP progress notifications if the client supports them
  (subscribe to bridge job progress — needs hook H5).

### 2.3 Why it is a thin layer

Everything an MCP server needs is already exposed by the bridge's OpenAI endpoint (`thread` control
via `extra_body.web2api`) and admin API. No extension or protocol changes are needed beyond the hooks
below.

---

## 3. Hooks v1 must include (so the above is possible without redesign)

| ID | Hook | Where specified | Status in v1 plan |
|---|---|---|---|
| H1 | Selectors/URLs/signals as data with validated hot overrides | `05` §2 | Phase 2/6 |
| H2 | Health reports with failing keys and resolution tiers | `04` §9 | Phase 6 |
| H3 | Redacted DOM snapshots on demand | `04` §9.3 | Phase 6 |
| H4 | **Redacted stream sample capture**: in debug mode, the net tap can record the raw chunks of one job's completion stream (max 1 MB), with a redaction pass that replaces the answer text with same-length `x` runs while keeping JSON structure/keys. Request via a new request/response pair `STREAM_SAMPLE_REQUEST {providerId}` → arms capture for the next job → `STREAM_SAMPLE_RESULT`. | add to `06` §6 | Phase 6 (stretch) |
| H5 | Job progress subscription for non-HTTP consumers: `GET /web2api/jobs/{id}/events` (SSE of phases) | add to `07` §9 | Phase 6 (stretch) |
| H6 | **Dry-run probe with a candidate config**: `HEALTH_PROBE {providerId, candidatePatch}` — the tab evaluates critical keys using the effective config + patch without persisting anything | `06` §6 | Phase 6 |
| H7 | Admin API for config get/override/revert, probes, snapshots, reports | `07` §9 | Phase 6 |
| H8 | Configs versioned (`configVersion`, `overrideVersion`, `baseConfigVersion`) | `05` §2 | Phase 2 |
| H9 | Fixture layout per provider in the repo (`tests/fixtures/<id>/`) usable by an automated agent | `05` §4, `09` §3 | Phase 1 |
| H10 | Net-vs-DOM divergence warnings as a parser drift signal | `04` §5.7 | Phase 4 |
