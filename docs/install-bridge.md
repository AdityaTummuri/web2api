# Install the bridge

The bridge is the small local program that exposes the OpenAI-compatible API and talks to the
extension. Two ways to get it — both give the **same program with the same commands**.

> Target-state guide (see README status note). Parts marked *(Phase 7)* depend on the productization phase.

## Option A — Standalone binary (no Python needed)

1. Download the file for your system from the project's Releases page:

   | System | File |
   |---|---|
   | Linux x86-64 / ARM64 | `web2api-bridge-<version>-linux-x86_64` / `-linux-aarch64` |
   | macOS Apple Silicon / Intel | `web2api-bridge-<version>-macos-arm64` / `-macos-x86_64` |
   | Windows 64-bit | `web2api-bridge-<version>-windows-x86_64.exe` |

2. **Verify it** (recommended): download `SHA256SUMS` and its signature from the same release, then
   `sha256sum -c SHA256SUMS --ignore-missing` (Linux), `shasum -a 256 -c …` (macOS), or
   `Get-FileHash` (Windows PowerShell). Signature verification command and public key are in the
   release notes.
3. Put it somewhere permanent and make it executable:
   * Linux/macOS: `chmod +x web2api-bridge-*` and move it to e.g. `~/.local/bin/web2api-bridge`.
   * Windows: put the `.exe` in e.g. `%LOCALAPPDATA%\Programs\web2api\` (and add that to `PATH` if you like).
4. First-run notes:
   * **macOS** may say the app is from an unidentified developer. Either allow it in
     *System Settings → Privacy & Security*, or run `xattr -d com.apple.quarantine ~/.local/bin/web2api-bridge`.
   * **Windows** SmartScreen may warn about an unrecognised app. Choose *More info → Run anyway* only
     after checking the checksum.
5. Faster-starting variant: a `-dir` archive (unzip, run the `web2api-bridge` inside) starts instantly;
   the single file unpacks itself on each start (1–2 s).

## Option B — Python

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv tool install web2api-bridge      # install
uv tool upgrade web2api-bridge      # update later
# or try without installing:
uvx web2api-bridge
```
Prefer pip? `pipx install web2api-bridge` works too.

From a git checkout (developers): `cd bridge && uv sync && uv run web2api-bridge`.

## First run

```bash
web2api-bridge
```
You will see something like:
```
Web2API bridge 1.0.0 listening on http://127.0.0.1:8787
  OpenAI base URL : http://127.0.0.1:8787/v1
  API key         : sk-w2a-9fKq…        (shown once; new keys: web2api-bridge keys create --name NAME)
  Pairing token   : w2a_pair_…          (paste into the extension popup; `web2api-bridge pairing show`)
```
* **Copy the API key now** — only a hash is stored. Lost it? `web2api-bridge keys rotate default`.
* The **pairing token** goes into the extension popup (see the Chrome/Firefox guides).
* The bridge only listens on `127.0.0.1` (your computer). Don't change this.

## Run it automatically at login *(Phase 7)*

```bash
web2api-bridge service install     # per-user, no admin/root needed
web2api-bridge service status
web2api-bridge service restart
web2api-bridge service uninstall
```

| OS | What gets created |
|---|---|
| Linux | systemd *user* unit `~/.config/systemd/user/web2api-bridge.service` (restarts on failure) |
| macOS | LaunchAgent `~/Library/LaunchAgents/dev.web2api.bridge.plist` (KeepAlive) |
| Windows | Task Scheduler task "at log on" for your user, restarts on failure |

The installer prints exactly what it created. Logs: see `service status` for the path (rotating files,
no prompt/answer text unless you turn that on).

## Where things are stored

| | Linux | macOS | Windows |
|---|---|---|---|
| Config (keys, pairing token, `config.toml`) | `~/.config/web2api/` | `~/Library/Application Support/web2api/` | `%APPDATA%\web2api\` |
| State (logs, thread map) | `~/.local/state/web2api/` | `~/Library/Application Support/web2api/state/` | `%LOCALAPPDATA%\web2api\` |

## Configuration

Optional `config.toml` in the config directory (all keys have sensible defaults):
```toml
port = 8787                 # change only if 8787 is taken (then update the bridge URL in the extension popup)
history_mode = "normal"     # "temporary" = use each site's temporary/incognito chat where available
persist_threads = false     # remember which web chat continues which conversation across restarts
check_updates = false       # opt-in: look for new releases once a day (no data sent)
[timeouts]
total_ms = 300000           # longest a single answer may take
```
Environment variables `WEB2API_PORT`, `WEB2API_LOG_LEVEL` override the file. Full list: `spec/07-bridge-server-spec.md` §2.

## Uninstall

`web2api-bridge service uninstall`, delete the binary (or `uv tool uninstall web2api-bridge`), and
delete the config/state folders above to remove keys and logs.
