# 12 — Product Quality, Footprint, and Distribution

The goal is something the owner can **rely on daily**, not a demo. This document defines what that
means in concrete, testable terms: a footprint budget (lightweight), reliability engineering,
how it is installed (two ways: **from source** and **standalone binary**), how it runs unattended, how it
is updated, how problems are diagnosed, and what must be true before calling it 1.0.

Where this document conflicts with an earlier one on packaging, tooling or operations, **this one wins**.

---

## 1. What "product, not MVP" means here

| Quality | Concrete commitment |
|---|---|
| Installs in minutes | Option A: `uvx web2api-bridge` / `uv tool install web2api-bridge`. Option B: download one file, run it. Extension from the browser store (Chrome Web Store, Firefox AMO). No other prerequisites on Option B. |
| Survives restarts | Bridge runs as a per-user background service (auto-start at login, auto-restart on crash). Extension reconnects on its own. After a reboot the user does nothing. |
| Fails loudly and helpfully | Every error has a stable code, a plain-language "what to do", and shows in the popup, the API error body and the logs. No silent partial answers (L-11, L-12). |
| Self-diagnosing | `web2api-bridge doctor` checks the whole chain; `support-bundle` produces a redacted zip to attach to an issue; the popup has "Copy diagnostics". |
| Stable contract | SemVer; documented API; protocol and config versioning with compatibility checks in both directions (§7). |
| Bounded resources | No unbounded queues, buffers, logs, or storage. Soak-tested (§5.6). |
| Private | No telemetry, no network calls except to localhost (and, only if the user enables it, an update check). Documented in a privacy policy. |
| Maintainable | CI on every change; provider fixtures; health reports; the maintainer hooks from `11`. |

---

## 2. Footprint budgets ("very lightweight")

Budgets are **CI-enforced gates** (§8). If a change exceeds one, fix the change or raise the budget
explicitly in this document with a justification. Initial numbers are targets set from experience with
similar stacks; **Phase 3 must measure the real baseline and this table must be updated to the measured
values plus ~15 % headroom** (record in `spec/OPEN_QUESTIONS.md` → resolved).

| Component | Budget | How to keep it | Measured by |
|---|---|---|---|
| Bridge runtime dependencies | **1** (`aiohttp`) | Stdlib for everything else (`07` §1). Adding a dependency requires a written justification in the PR. | `uv tree` check in CI. |
| Bridge idle memory (RSS), no jobs | ≤ 60 MB | No import of heavy stdlib modules at startup; lazy imports for admin/support-bundle code; no per-request global caches without caps. | Start the bridge, wait 5 s, read RSS (`psutil`-free: `/proc/self/status` on Linux; `resource`/`ps` elsewhere) in CI on Linux. |
| Bridge memory under load | ≤ 150 MB with 20 queued jobs and 5 MB prompts | Caps in `08` §3.6; bounded job history ring (500 entries); no text in history. | Load test in CI. |
| Bridge cold start to `/healthz` | ≤ 1.0 s from source; ≤ 2.5 s binary (onefile unpack) | Lazy imports; onedir option for faster start (§3.4). | CI timer. |
| Bridge idle CPU | ~0 % (no busy loops; only the 10 s watchdog and 20 s heartbeats) | Event-driven only. | 60 s sample in CI: < 1 % of one core. |
| Standalone binary size | ≤ 25 MB (Linux/macOS), ≤ 30 MB (Windows) | PyInstaller `--exclude-module` for `tkinter`, `unittest`, `pydoc`, `email.*` unused, `xml`, `sqlite3`, `curses`, `distutils`, etc.; no UPX (antivirus false positives). | CI size check. |
| Extension package (zip) | ≤ 300 KB | Vanilla JS, no framework, no bundler, no bundled fonts/images beyond 2 icons, minified only if it stays readable by the maintainer (default: **not minified**; stores accept readable code). | CI size check. |
| Extension idle cost on a provider page | No timers, no polling; observers only attach while a job runs; ≤ 1 ms of main-thread work per page load beyond the net-tap handshake | Event-driven design (`04` §5.2, §6.4). The MutationObserver for SPA navigation (`04` §5.1) must early-exit when `location.href` is unchanged. | Manual profile in Phase 6 (Performance panel) + a unit test asserting no `setInterval` is ever registered in content scripts. |
| Extension background idle | Zero work between 20 s heartbeats | Heartbeat is the only periodic work. | Code review rule + test that lists registered timers. |
| Extension permissions | Minimal set from `08` §4.1 | See §9.3 for per-provider optional host permissions. | Manifest lint in build script. |

---

## 3. Bridge distribution: two options

### 3.1 Option A — from source / PyPI (for people with Python)

* Publish `web2api-bridge` to PyPI. Install: `uv tool install web2api-bridge` (recommended), or
  `pipx install web2api-bridge`, or run once with `uvx web2api-bridge`.
* Upgrades: `uv tool upgrade web2api-bridge`.
* The wheel contains only `web2api_bridge/` (+ the provider JSON Schema file). Python ≥ 3.11.
* Developers: `git clone`, `cd bridge && uv sync && uv run web2api-bridge`.

### 3.2 Option B — standalone binary (no Python needed)

* One executable per platform: `web2api-bridge-<version>-linux-x86_64`, `-linux-aarch64`,
  `-macos-arm64`, `-macos-x86_64`, `-windows-x86_64.exe`.
* Same code, same CLI, same behaviour as Option A. A test in CI runs the **identical integration
  test-suite against the frozen binary** (start binary on a random port; run the fake-extension
  scenarios against it) so "works from source" can never drift from "works as binary".
* Built with **PyInstaller** (`--onefile`, `--name web2api-bridge`, `--strip` on Linux/macOS). Rationale:
  mature, supports all three OSes, handles aiohttp's C extensions. Evaluate **Nuitka** later if startup
  time or size budgets cannot be met; keep the build behind a single script so swapping tools doesn't
  touch the code.
* `bridge/packaging/build_binary.py` (stdlib only + calls PyInstaller): sets
  `--exclude-module` list, embeds version from `web2api_bridge/__init__.py`, includes the schema file
  as data (`--add-data`), and writes the artifact to `bridge/dist/`.
* PyInstaller cannot cross-compile: each platform binary is built on a native GitHub Actions runner
  (`ubuntu-24.04`, `ubuntu-24.04-arm`, `macos-14` (arm64), `macos-13` (x86_64), `windows-2022`). Linux
  binaries are built on the oldest practical runner glibc to maximise compatibility (document the
  minimum glibc in the release notes; offer the source option for older distros).
* **Code in the binary must not use `__file__`-relative data lookups**; load packaged data through
  `importlib.resources` and make PyInstaller see it (hidden-import/data flags in the build script).
  A CI test runs the binary and asserts `GET /web2api/status` reports the bundled schema version.

### 3.3 Integrity and trust

Releases are what users run with access to their AI accounts; they must be verifiable.

* Every release asset has a SHA-256 in `SHA256SUMS`, and `SHA256SUMS` is signed (minisign or Sigstore
  `cosign sign-blob`; document the verification command and public key in the README).
* macOS: sign with a Developer ID and notarize if the owner has an Apple developer account; otherwise
  document `xattr -d com.apple.quarantine` and expect friction — **record this as an owner decision**
  in `OPEN_QUESTIONS.md`.
* Windows: unsigned binaries trigger SmartScreen warnings. Options: code-signing certificate, or
  Microsoft Trusted Signing, or document the warning. **Owner decision.**
* Build with pinned dependency versions (`uv.lock`), pinned PyInstaller version, and GitHub Actions
  pinned by commit SHA. Publish the build provenance (GitHub artifact attestations) if available.
* Do **not** compress with UPX.

### 3.4 Startup time: onefile vs onedir

`--onefile` unpacks to a temp dir on every start (~1–2 s, plus antivirus scans on Windows). Provide:
* `web2api-bridge-<v>-<platform>` — onefile (simple, single download).
* `web2api-bridge-<v>-<platform>-dir.tar.gz|zip` — onedir (instant start; used by installers/services).
`service install` (§4) prefers the onedir layout when present beside the executable, else onefile.

---

## 4. Running unattended: user-level service

CLI (adds to `07` §2.1):

```
web2api-bridge service install [--port N]   # register + start at login
web2api-bridge service uninstall
web2api-bridge service status               # installed? running? last exit code? log path
web2api-bridge service restart
web2api-bridge --version                    # prints bridge version, protocol version, python/frozen
web2api-bridge doctor                       # §6.1
web2api-bridge support-bundle [-o path]     # §6.2
```

`service install` works for **both** the source and binary installs: it records the absolute path of
the running executable (`sys.executable -m web2api_bridge` when from source, `sys.executable` when
`sys.frozen`) and writes a per-user unit. **No root/admin required.**

| OS | Mechanism | File / location | Restart policy |
|---|---|---|---|
| Linux | systemd **user** unit | `~/.config/systemd/user/web2api-bridge.service`; `systemctl --user enable --now` | `Restart=on-failure`, `RestartSec=2`, `StartLimitBurst` generous; `loginctl enable-linger` is mentioned in docs (service then runs without an active login — not needed since the browser needs a session anyway). Hardening: `NoNewPrivileges=yes`, `PrivateTmp=yes`, `ProtectSystem=strict`, `ReadWritePaths=<state dir> <config dir>`. |
| macOS | launchd **LaunchAgent** | `~/Library/LaunchAgents/dev.web2api.bridge.plist`; `launchctl bootstrap gui/$UID …` | `KeepAlive` = true, `ThrottleInterval` 5. |
| Windows | Task Scheduler task, trigger "At log on of current user", **restart on failure** every 1 min up to 999 times, "run only when user is logged on", hidden window | Created with `schtasks /Create` (no admin needed for a user-level task) | As configured. |

Each installer prints exactly what it created and how to remove it. Idempotent: re-running updates the
unit in place. Logs go to the state dir (§5.3), not the journal only.

Port conflicts: if the port is taken, the bridge exits with a clear message naming the owning process
when discoverable, never silently picks another port (the extension's configured URL would be wrong).
`--port` / config changes require updating the popup's bridge URL; `doctor` flags mismatches it can see.

---

## 5. Reliability engineering

### 5.1 Design principles

1. **Crash-only:** any component can be killed at any time and the system recovers by restarting it.
   No "clean shutdown required" state. State on disk (token files, thread map) is written
   atomically: write temp file in the same dir → `fsync` → `os.replace`.
2. **Everything has a timeout** (HTTP handlers, WebSocket handshake, extension acks, probes,
   snapshots, cancellation). Timeouts are named constants in one place per side.
3. **Everything is bounded:** job history ring (500), delta reorder buffer (≤ 1000 frames/job),
   pending requests (≤ 20 per provider), health reports ring (100 bridge / 50 extension), snapshots
   (10 × ≤ 2 MB), logs (rotation §5.3), thread map (1000 LRU).
4. **No silent degradation:** a fallback that changes behaviour (net → DOM, retry on another tab)
   is recorded in the response's `web2api.warnings` and in logs.
5. **Idempotent protocol operations:** duplicate `JOB_CANCEL`, duplicate `PROVIDERS_UPDATE`, replayed
   `JOB_DELTA` are harmless (`06`).
6. **Backpressure over buffering:** SSE writes `await resp.write(...)` and respect drain; if a client
   is too slow (write blocked > 30 s) → cancel the job and drop the client.

### 5.2 Failure matrix (each row needs an automated or scripted test)

| Failure | Expected behaviour | Test |
|---|---|---|
| Bridge process killed mid-job | Service restarts it < 5 s; extension reconnects with backoff; in-flight client gets a connection error; next request works; the abandoned generation in the tab is stopped when the tab-pool verifies it dirty. | Scripted (Phase 5 manual + fake-extension test for reconnect). |
| Extension reloaded/updated mid-job | Bridge: `EXTENSION_RESTARTED` (retry-eligible if not submitted). Extension: marks tabs dirty, re-verifies. | Integration + manual. |
| Browser quit | Bridge reports `NO_EXTENSION` (503) with a message to open the browser; `/v1/models` empty. | Integration. |
| Worker tab closed by the user | `TAB_LOST`; pool opens a fresh tab for the next job. | DOM/integration (stub chrome.tabs). |
| Provider logs the user out | `LOGIN_REQUIRED` within 5 s; provider status `login_required`; clear popup hint. | DOM fixture + manual. |
| Captcha/Cloudflare page | `CAPTCHA_REQUIRED`; tab is left visible for the user (dedicated window can be focused via popup button "Show worker window"). | Manual. |
| Provider rate limit | `RATE_LIMITED` (+ `Retry-After` when parseable); provider cool-down: pool refuses new jobs to that provider until the banner clears or `retryAfterSec` elapses (prevents hammering). | DOM fixture + unit. |
| Selector break (site redesign) | `SELECTOR_NOT_FOUND` + health report + snapshot; provider `unhealthy`; other providers unaffected; override can fix without release. | Manual (broken override). |
| Network offline | Provider page error state → `PROVIDER_ERROR`; no hang past `firstTokenMs`. | Manual. |
| Client sends 5 MB prompt | Accepted up to limits; above → 400 `PROMPT_TOO_LONG`; memory stays within budget. | Load test. |
| Client disconnects mid-stream | `JOB_CANCEL`; tab recovers; no leaked job. | Integration. |
| Slow client | Backpressure rule (§5.1.6). | Integration with throttled reader. |
| Clock jumps (laptop sleep/resume) | The bridge measures deadlines with `time.monotonic`. The extension schedules deadlines with `setTimeout` and also stores the absolute deadline (`Date.now()` based) in `jobs.active`; on every wake-up (alarm, port event) it checks stored deadlines and fails any job already past its deadline immediately, so a laptop resuming from sleep never leaves a zombie job. | Unit. |
| Disk full / unwritable state dir | Bridge keeps running (in-memory only), logs a warning, `doctor` reports it. | Unit (temp dir read-only). |
| Corrupt state file | Ignored with a warning; file renamed `*.corrupt-<ts>`; fresh state. | Unit. |
| Two bridges started | Second exits (port in use) with a clear message; no state-file corruption (state files are only written by the process that bound the port; take an advisory lock file `<state>/bridge.lock` using `fcntl.flock`/`msvcrt.locking`). | Unit/integration. |

### 5.3 Logging

* Bridge logs to **stderr** and to a rotating file in the state dir:
  `web2api-bridge.log`, `RotatingFileHandler(maxBytes=1_000_000, backupCount=4)`.
* Format: single-line, `ts level event key=value …`. Levels as in `07` §10. Never prompt/answer text
  by default.
* The extension keeps the last 500 log lines in memory (ring) for "Copy diagnostics".

### 5.4 Resource hygiene checklist (review gate for every PR touching the bridge)

- [ ] No unbounded `list`/`dict`/`asyncio.Queue` growth.
- [ ] Every `asyncio.create_task` is stored and cancelled on shutdown; exceptions are logged
      (`task.add_done_callback`).
- [ ] No blocking calls in the event loop (file I/O of tokens/state is small, but use
      `loop.run_in_executor` for anything > 1 ms such as bundle creation).
- [ ] No global mutable singletons except those in `app[...]`.

### 5.5 Extension equivalents

- [ ] All state reloadable after service-worker restart (`04` §3.2).
- [ ] No `setInterval` in content scripts; background timers listed in one module for testing.
- [ ] Ports cleaned up on `onDisconnect`; `WeakMap`/`WeakSet` for DOM references.
- [ ] Every storage write is size-capped.

### 5.6 Soak and chaos testing (before 1.0 and before each minor release)

* **Soak:** 24 h run with the fake extension and a client sending a request every 30 s with random
  sizes; assert RSS growth < 10 % after warm-up, zero leaked jobs/tasks, log file rotation worked, no
  errors. Script: `bridge/scripts/soak.py` (stdlib client).
* **Live soak (manual):** 6 h with a real provider tab, 1 request / 5 min; assert no stuck state and
  no account warnings.
* **Chaos:** randomised kill/restart of the bridge, extension reload, tab closure, WebSocket drops (a
  tiny TCP proxy in the test harness that cuts connections), malformed frames. Invariants: no crash, no
  stuck job, every client request ends in a terminal response within its deadline.
* **Fuzz:** stream parsers and the SSE splitter fed random/truncated/oversized input — must never throw
  or loop (property-style tests with a seeded PRNG; no external fuzzing library).

---

## 6. Diagnostics

### 6.1 `web2api-bridge doctor`

Prints a checklist and exits non-zero if anything is red. Checks (each with ✔/✘ and a fix hint):
1. Version info (bridge, protocol, Python/frozen, OS).
2. Config and state dirs exist and are writable; token files exist with correct permissions
   (POSIX 0600; on Windows, the file is inside the user profile — report if ACLs allow others).
3. Port available, or already served by *this* bridge (`/healthz`).
4. If running: extension connected? protocol versions compatible? extension version vs bridge version
   (§7). Providers: status per provider and tab counts. Last 5 failure codes per provider.
5. Service: installed? running? (per OS).
6. Optional: `--probe` runs `HEALTH_PROBE` for all providers.

### 6.2 `web2api-bridge support-bundle`

Creates `web2api-support-<timestamp>.zip` containing: version info, `doctor` output, last 1 MB of
logs, the bridge's recent job metadata (no text), health reports (already content-free), provider
config versions/override versions, and the redacted snapshot(s) if the user passes `--snapshots`.
**Excludes tokens and any prompt/answer text.** A unit test greps the produced zip for the token
strings and for a canary prompt text and asserts neither appears.

### 6.3 Popup "Copy diagnostics"

JSON with extension version, browser, protocol version, bridge URL (token redacted), connection state
+ last close code/reason, per-provider status, last 20 log lines (redacted), last 5 health reports.

### 6.4 Error experience

Every `Web2APIError.message` has the form: *what happened* + *what to do*. Docs have one page
`docs/errors.md` with every code from `06` §7, its cause, and the fix; error bodies include
`web2api.docs: "https://…/errors#LOGIN_REQUIRED"` (URL configurable; defaults to the repo docs).

---

## 7. Versioning and compatibility

Four independent version numbers:

| Thing | Format | Where |
|---|---|---|
| Bridge | SemVer `MAJOR.MINOR.PATCH` | `web2api_bridge/__version__`, `pyproject.toml` |
| Extension | SemVer (stores need `a.b.c`) | `manifests/base.json` |
| Wire protocol | integer major | `06` |
| Provider config | `configVersion` `YYYY.MM.DD-N`, schema integer | `05` |

Rules:
* HTTP API: changes within a major version are additive only. Breaking changes → major bump.
* Bridge ↔ extension: compatible iff `protocolVersion` majors are equal. Beyond that, each side
  advertises `minPeerVersion`/`version` in `HELLO`/`WELCOME` (add fields `minPeerVersion` to both —
  update `06` §3.1 when implementing). If the peer is older than `minPeerVersion` → the popup/doctor
  show "Update the bridge/extension to ≥ X" and the bridge refuses jobs with a clear error rather than
  misbehaving.
* Releasing: the bridge and extension are tagged together (`vX.Y.Z`) when the protocol changes;
  otherwise they may release independently. A **compatibility matrix** table lives in the README and
  is updated per release.
* Deprecations: announced in release notes one minor version ahead; API fields are never silently
  removed.
* Changelog (`CHANGELOG.md`, Keep a Changelog format) is updated in every PR that changes behaviour.

### 7.0 Release lineup

| Release | Content |
|---|---|
| **1.0.0** | OpenAI-compatible API + extension (Chrome, Firefox) + bridge (source and binary) — everything in `10` Phases 0–7 |
| 1.x | Tier-2 providers, fixes, provider-config updates |
| **2.0.0** | MCP server, tasks API, Deep Research, search mode, utility lane, CLI companions (`14`, `10` Phase 10). `/v1` stays backward compatible; protocol major stays 1 |

The step-by-step runbook for cutting a release is `RELEASING.md` at the repo root.

### 7.1 Updating

* **Extension:** via store auto-update (Chrome Web Store, AMO). Bundled provider configs update with
  it; overrides pointing at an older `baseConfigVersion` are dropped and reported (`05` §2.4).
* **Bridge, Option A:** `uv tool upgrade`. **Option B:** download the new binary; `service restart`.
* **Update notification (opt-in, off by default):** `check_updates = true` makes the bridge query the
  GitHub Releases API at most once per 24 h (no identifiers sent) and show a notice in `doctor`,
  `/web2api/status` and the popup. No auto-download or self-replacement in 1.0 (avoids a whole class of
  supply-chain and permission problems).
* Config/state migrations: files carry `schema` numbers; the bridge migrates forward on start and
  keeps a `.bak` of the previous file.

---

## 8. CI and release pipeline (GitHub Actions)

On every push/PR:
1. **Extension:** `npm ci` → `npm test` → `npm run build` → manifest lint (permissions equal the allowed
   list in `08` §4.1; no `web_accessible_resources`; no remote URLs in scripts; no `eval`/`new
   Function`) → package size check.
2. **Bridge:** `uv sync --frozen` → `ruff check` (dev-only tool, configured in `pyproject.toml`) →
   `uv run pytest` → dependency check (`uv tree` shows exactly `aiohttp` and its transitive set;
   fail on new top-level deps) → startup/RSS/idle-CPU budget checks (Linux job).
3. **Parity:** protocol constants and schema copies identical (`09` §2.6).
4. **Cross-platform smoke:** matrix (ubuntu, macos, windows): `uv run pytest -m smoke` (a fast subset
   that starts the bridge and talks to it with the fake extension).

On tag `vX.Y.Z`:
1. Build binaries on the native runner matrix (§3.2) → run the **full integration suite against each
   binary** → size/startup budget checks.
2. Build `dist/chrome` and `dist/firefox` zips; for Firefox also run `web-ext lint` (dev tool via
   `npx`, not a project dependency).
3. Build wheel + sdist; `uv publish` to PyPI (trusted publishing, no long-lived token).
4. `SHA256SUMS` → sign → upload with binaries, extension zips, and release notes extracted from
   `CHANGELOG.md`.
5. (Manual gate) Submit extension zips to the Chrome Web Store and AMO (§9).

Branching: `master` always releasable; tags for releases; conventional commits.

---

## 9. Extension store readiness

### 9.1 Why this matters

* **Firefox release builds only run signed extensions.** A temporary add-on disappears when Firefox
  restarts, which would make the product unreliable. The extension must be signed via AMO (an
  **unlisted** channel is enough if the owner doesn't want a public listing; listed is better for
  discoverability and auto-updates).
* **Chrome:** loading unpacked works but shows a "disable developer mode extensions" prompt at
  startup and doesn't auto-update. Publishing to the Chrome Web Store (unlisted or public) removes this.
* Both stores require a **privacy policy** and justification of host permissions. This product
  collects nothing, sends nothing off-machine (only to `127.0.0.1`), and says so.

### 9.2 Store checklist

- [ ] Privacy policy page (`docs/privacy.md`): no data collection; what is stored locally and where;
      how to wipe it.
- [ ] Permission justifications text for each permission and each host.
- [ ] Single purpose statement: "Lets local applications use the AI chat sites you are logged into
      through a local bridge."
- [ ] No remote code (satisfied by design; rule 3 in `00`).
- [ ] Screenshots, 128×128 icon (add `icon-128.png`; the prototype has 48/96 only), short/long
      description. Not affiliated with OpenAI/Anthropic/Google disclaimer; product name must not imply
      affiliation (avoid "ChatGPT"/"Claude" in the extension *name*; naming them in the description to
      identify supported sites is fine).
- [ ] Chrome: stable extension id via the manifest `key` (needed for origin pinning, `08` §3.2).
- [ ] Firefox: `browser_specific_settings.gecko.id`, and `data_collection_permissions` declaration if
      required by the AMO policy current at release time (check; it changed in 2025).
- [ ] Reviewer notes explaining that testing requires a local bridge and logged-in accounts (stores
      reject unexplained extensions); provide a short screen recording.

### 9.3 Optional host permissions per provider (recommended)

Instead of requesting every provider's host permission at install, declare them as
`optional_host_permissions` and request each when the user enables that provider in the popup
(`chrome.permissions.request`). Content scripts for enabled providers are then registered dynamically
with `chrome.scripting.registerContentScripts` (persisted across sessions) — including the MAIN-world
net tap at `document_start`. Benefits: install prompt says almost nothing scary; users only grant what
they use; store review is easier. Cost: a little more code (enable/disable flow) and the dynamic
registration must be re-validated on browser update. **Decision for the implementer:** implement
static manifest generation first (Phase 2–5, simplest, matches `04` §2.3), and convert to optional
permissions in the productization phase (`10`, Phase 7) behind the same provider-config data.

---

## 10. Support policy and project hygiene

* **Supported:** the two latest stable Chrome (and Chromium-based: Edge, Brave) and Firefox
  versions; Windows 10+, macOS 12+, Linux with glibc ≥ the build runner's (documented).
* **Provider support table** in `docs/providers.md`: provider, tier, status (verified / experimental /
  broken), net-tap yes/no, **date last verified and by whom/what (human or maintainer run)**. Stale
  entries (> 30 days) render as "unverified" via a small script in CI that fails the docs build on
  missing dates.
* **Repository files:** `LICENSE` (the owner must choose; MIT is the default assumption — confirm in
  `OPEN_QUESTIONS.md`), `README.md`, `CHANGELOG.md`, `SECURITY.md` (private reporting address; scope:
  the local bridge and extension), `CONTRIBUTING.md` (how to add a provider — `05` §6), issue
  templates (bug report asks for `doctor` + support-bundle output), `docs/` (install, providers,
  errors, privacy, troubleshooting, API reference).
* **Terms-of-service honesty:** README and the store listing say plainly that automating consumer chat
  websites may violate provider terms and can lead to rate limiting or account action (L-47), and that
  the project is not affiliated with the providers.
* **Telemetry:** none. Never add any without a spec change and an explicit opt-in.

---

## 11. Definition of done for 1.0

All must be true:

- [ ] Phases 0–7 of `10-implementation-plan.md` complete, acceptance criteria passing.
- [ ] Tier-1 providers (ChatGPT, Claude, Gemini) pass the live smoke test in Chrome **and** Firefox,
      three consecutive runs, within the previous 7 days.
- [ ] CI green on all platforms; binaries pass the full integration suite; budgets met.
- [ ] 24 h soak and chaos tests passed (§5.6).
- [ ] Service install verified on Linux, macOS and Windows from a clean user account, including
      reboot survival.
- [ ] `doctor` and `support-bundle` verified (including the no-secret-leak tests).
- [ ] Extension published (at least unlisted) on the Chrome Web Store and signed on AMO; installs
      and updates without developer mode.
- [ ] Release artifacts checksummed and signed; verification instructions tested by someone other than
      the builder.
- [ ] Docs complete (§10 list); a person new to the project reaches a successful call in ≤ 10 minutes
      following the README (time it).
- [ ] Open owner decisions recorded and resolved: license, macOS signing, Windows signing, store
      accounts, project/repo name (the prototype name "Web2API Pro" and store naming rules).
