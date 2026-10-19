# Developer chores on the free fast model

> **Planned for release 2.0.0** — target-state guide (see README status note). Design:
> `spec/14-mcp-server-v2.md` §3.8–3.12, §5, §11.3.

Commit messages, PR descriptions, summaries and docs are perfect for a fast, effectively free model:
they're low-stakes and token-hungry. Web2API routes them to its **utility lane** — by default Gemini
Flash-Lite through your browser — so your main coding assistant (and its token budget) stays focused on
real work. Fallbacks (ChatGPT, Claude) kick in if the primary is rate-limited.

> "Effectively free" depends on your account and the site's current limits; the lane handles
> rate limits by falling back and reports when nothing is available.

You can use the chores three ways: **ask your MCP assistant**, **use a slash command**, or **use the
terminal commands** (no MCP needed).

## Commit messages

**MCP:** "Write a commit message for my staged changes" or the `/commit` prompt — the assistant runs
`git diff --staged` and calls `commit_message`.

**Terminal:**
```bash
git add -p
web2api-bridge commit                # prints a Conventional-Commits message
web2api-bridge commit --apply        # …and runs `git commit` with it
web2api-bridge commit --style plain --context "fixes the flaky login test"
```
**Automatic with a git hook** (per repository):
```bash
web2api-bridge git-hook install      # adds a prepare-commit-msg hook
```
When you run plain `git commit` with no message, the editor opens pre-filled with a generated message
that you can edit. The hook has a 20-second limit and **never blocks or breaks a commit** — if the
bridge is down or limited it silently does nothing. Skip it once with `WEB2API_HOOK=0 git commit`, disable
for a repo with `git config web2api.hook false`, remove with `web2api-bridge git-hook uninstall`.

What you get: `type(scope): subject` (≤ 72 characters, imperative, no trailing period), a wrapped body
explaining *why*, `BREAKING CHANGE:` footer when relevant. It's checked mechanically and retried once if
the model's format was off. Pass `recent_subjects` (the assistant does this automatically with
`/commit`) to match your repo's style.

## Pull request descriptions

"Write a PR description for this branch" / `/pr` → `pr_description` from the diff or commit list; returns a
title and a body (Summary, Changes, Testing notes, Risks) or fills in your PR template if you give one.

## Summaries
`summarize` takes long text (logs, articles, meeting notes, code), any length: very long input is
summarised in pieces and combined. Choose `length` (short/medium/long) and `format` (bullets/paragraph).

## README and docs generation

**MCP:** "Generate a README for this project" or `/readme`. The assistant reads your key files and calls
`generate_docs`; you review and save the result.

**Terminal:**
```bash
web2api-bridge docs readme .                 # print a README for the current repo
web2api-bridge docs readme . --write         # write README.md (asks before overwriting)
web2api-bridge docs generate architecture .  # kinds: readme, api_reference, architecture,
web2api-bridge docs generate docstrings src/ #        docstrings, changelog, contributing, custom
web2api-bridge docs readme . --quality best  # fast model reads the code, a stronger model writes the final text
```
How it works: files are picked via `git ls-files` (so `.gitignore` is respected; lockfiles, binaries,
vendored and generated files skipped; manifests and entry points first). Big projects are summarised in
chunks, then composed into the final document, then checked (required sections present, code fences
balanced, no placeholders, mentioned file paths exist). It returns text; **you** decide what to save.
Updating an existing doc: pass it as `existing` (CLI: it reads the current file automatically).

Quality tips: the fast model is great for structure and factual summaries of code, less so for polished
prose — use `--quality best` for a README you'll publish, and always skim for mistakes.

## Safety and privacy
* Everything you send goes to the provider's website (Gemini by default) — don't send code you aren't
  allowed to share with that service.
* A secret scanner runs first: private keys, cloud/API tokens, passwords, `.env` lines, JWTs and URLs
  with credentials are replaced by `[REDACTED:kind]` (`on_secrets: "refuse"` blocks instead). It's a
  safety net, not a guarantee.
* Chore chats use the site's temporary/no-history mode where available.
* Rate limits: chores are paced (about 1.5 s apart) and capped (20/minute) so a runaway script can't hammer
  your account.
