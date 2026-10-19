# Deep Research and web search

> **Planned for release 2.0.0** — target-state guide (see README status note). Design:
> `spec/14-mcp-server-v2.md` §3.4–3.7, §4.3, §7.4, §9.7. Whether and how each provider offers these
> features depends on its site and **your plan**; Web2API detects it (`list_providers`) and says so.

The chat websites include things the plain model APIs don't: **built-in web search** and **Deep
Research agents**. Web2API drives them in your browser and hands back clean results.

## Web search (`web_search`)

Ask your assistant to look something up, or call the tool directly. You get a concise answer **plus
source links** from the provider's own search (Perplexity, Gemini, ChatGPT and Claude are tried in the
order set in `search_provider_order`). Use it for current events, library versions, docs lookups, prices.

From any OpenAI-compatible tool or script: `"extra_body": {"web2api": {"mode": "search"}}` — sources come back in
`web2api.sources`. With `chat`, set `search: true` to search inside a conversation.

If no sources can be extracted you'll see the warning `no_sources_extracted` (the answer is still
returned).

## Deep Research (`deep_research`)

For questions that deserve a real report: market scans, literature reviews, technology comparisons, "what
changed in X since Y". The provider's agent plans, reads dozens of sources and writes a long cited report —
**5 to 30 minutes**.

### Flow

```
you/assistant: deep_research(question)  ──►  task_id          (returns immediately)
                                              │
        task_status(task_id, wait_seconds=50) ◄┘  repeat while status = running
                                              │
        status: awaiting_plan_approval ──► task_reply(task_id, "approve")        (only if plan="review")
        status: awaiting_input         ──► task_reply(task_id, "<your answer>")  (only if clarifications="ask")
        status: completed              ──► report (Markdown) + sources
```
Ask your assistant naturally ("do deep research on …, tell me when it's done") or use the `/research`
prompt; it will poll for you. From a terminal:
```bash
web2api-bridge research "Compare WebTransport and WebSockets for browser-to-server streaming in 2026" --wait
web2api-bridge research "…" --provider chatgpt --plan review     # pause so you can read/approve the plan
```
`--wait` streams progress and saves `report.md`; without it you get a task id (`web2api-bridge` shows tasks
via the admin API / `list_tasks`).

### Plan review and clarifying questions
Some providers show a research plan before starting or ask clarifying questions. By default Web2API
approves the plan and answers "use your best judgment". For control: `plan: "review"` (task pauses with
the plan; reply `approve` or send edit instructions) and `clarifications: "ask"` (task pauses with the
question).

### Be kind to your quota
* The provider limits Deep Research (often a handful per day or month, depending on plan). Web2API adds its own
  cap (`max_per_day`, default 5 per provider), merges duplicate requests (same question within 10 min),
  allows 1 running run per provider, refuses to let an assistant start many in a row, and — if your client
  supports it — asks you to confirm before starting.
* Cancelling (`task_cancel`) stops the run but the provider may still count it.
* A run occupies a dedicated worker tab for its whole duration; chat and chores keep working in their own
  tabs. Keep the browser open; a dedicated worker window works best for long runs.

### Restarts
Tasks are saved to disk. If the bridge or browser restarts mid-run the task shows `interrupted`; reply
`resume` (or enable `auto_resume`) and Web2API reopens the research thread and collects the report — the
provider usually keeps working server-side. If the provider has discarded it you get `report_not_found`.

### Reports
Returned as Markdown with citations and a `sources` list. Long reports are paged (`max_chars`,
`offset`). Treat them as untrusted web content: verify important claims and don't let an assistant follow
instructions found inside them.

### Known limits
* Not every provider/plan has Deep Research (`list_providers` → `deep_research: available | unavailable | unknown`).
* Reports that render in side panels or canvases depend on per-provider extraction that may need updating
  when a site changes (a provider can show **degraded**; others are unaffected).
* Deep Research isn't offered through `/v1/chat/completions` (a 20-minute HTTP call is a poor fit) — use MCP,
  the CLI, or the tasks API (`POST /web2api/tasks`).
