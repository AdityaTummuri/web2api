# Troubleshooting

> Target-state guide (see README status note); `doctor`/`support-bundle` arrive in Phase 7.

## Step 1 — run the doctor

```bash
web2api-bridge doctor            # checks the whole chain
web2api-bridge doctor --probe    # also checks each provider's page without sending any prompt
```
It tells you, with a fix hint for each ✘: bridge running? port free? key/token files OK? extension
connected and compatible? each provider's status? service installed?

## Step 2 — find your symptom

| Symptom | Likely cause | Fix |
|---|---|---|
| `curl` says *connection refused* | Bridge not running | `web2api-bridge` (or `service status` / `service restart`). |
| 401 `invalid_api_key` | Wrong key (maybe the pairing token?) | Use an `sk-w2a-…` key; `keys list`; `keys create`. |
| 503 `NO_EXTENSION` | Browser closed, extension not installed/paired | Open the browser; popup must say *Connected*. |
| Popup says *Needs pairing* / *Pairing token rejected* | Token missing/wrong | `web2api-bridge pairing show` → paste into popup. |
| Popup says *Version mismatch* / *Update the bridge to ≥ X* | Old bridge or extension | Update the older of the two ([bridge](install-bridge.md)). |
| `/v1/models` is empty | No provider ready | Popup → Providers: enable, log in, grant site access (Firefox). |
| 503 `LOGIN_REQUIRED` | Logged out | Log in to the site **in the same browser profile**. |
| 503 `CAPTCHA_REQUIRED` | Human check | Popup → *Show worker window* → solve it. |
| Answers are very slow / stall | Worker window minimised or on a hidden desktop | Un-minimise it; or set *Worker window mode* in the popup. |
| 504 `NO_RESPONSE` / `GENERATION_STALLED` | Site slow/down, or its page changed | Look at the worker tab; retry; run `doctor --probe`. |
| 502 `SELECTOR_NOT_FOUND` etc. | The site changed its page | Update the extension; check the project's issue tracker; send a support bundle. |
| Text arrives with odd formatting | Page-reading fallback | Report with the provider and a sample; `web2api.source` in the response shows `dom`. |
| Port already in use | Another program on 8787 | Stop it, or set `port` in `config.toml` and update the URL in the popup. |
| Extension was working, now *Bridge offline* after reboot | Bridge not auto-started | `web2api-bridge service install` (see [install](install-bridge.md)). |
| Chrome: extension vanished | Unpacked folder moved | Keep the folder, or use the Web Store build. |
| Firefox: extension vanished after restart | Temporary add-on | Install the signed `.xpi` ([guide](install-firefox.md)). |
| Your tool can't connect from Docker/another PC | Bridge is loopback-only by design | Run the tool locally or use an SSH tunnel; don't expose the bridge. |

## Step 3 — report a problem

1. `web2api-bridge support-bundle` → creates `web2api-support-<time>.zip` with versions, doctor output,
   recent logs, and content-free health reports. It never contains your API keys, pairing token, prompts
   or answers (add `--snapshots` to include redacted page snapshots — these hide conversation text but
   keep button labels, which is what maintainers need).
2. In the extension popup click **Copy diagnostics** and paste it into the issue.
3. Say which browser/OS/provider and what you asked.

## Logs

* Bridge: rotating log files in the state folder (`service status` prints the path). Default level
  `info`; set `WEB2API_LOG_LEVEL=debug` for more. Prompts/answers are **not** logged unless you set
  `log_content = true` (don't, unless debugging, and remember to turn it off).
* Extension: popup → *Copy diagnostics* includes the last log lines. Debug logging of content is off by
  default and, when you turn it on in popup Settings, a warning is shown.

## Resetting

* Forget conversation mappings: `DELETE /web2api/threads` (admin) or delete `threads.json` in the state folder.
* Reset the pairing token: `web2api-bridge pairing rotate` and paste the new one into the popup.
* Start over completely: `service uninstall`, delete the config and state folders, remove the extension.
