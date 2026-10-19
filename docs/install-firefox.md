# Install on Firefox

> Target-state guide (see README status note). Requires Firefox **128 or newer** (Firefox ESR 128+ is
> fine). Check at `about:support`. Details marked **(verify)** are confirmed during the platform spike
> (`spec/10-implementation-plan.md`, Phase 1) and this guide must be updated with the result.

Before you start, [install and start the bridge](install-bridge.md) and keep its **pairing token** handy.

## 1. Install the extension

### Signed add-on (recommended — survives restarts and auto-updates)
Firefox **release** builds only run extensions that Mozilla has signed.

* From Firefox Add-ons (AMO), once published: open the Web2API page → **Add to Firefox**.
* Or from the Releases page: download `web2api-<version>-firefox.xpi` (signed through AMO's
  unlisted channel), then open `about:addons` → gear icon → **Install Add-on From File…** → pick the file.

### Temporary install (development only)
1. Build: `cd extension && npm ci && npm run build:firefox` (output: `extension/dist/firefox`).
2. Open `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on…** → choose
   `extension/dist/firefox/manifest.json`.
3. **It is removed when Firefox restarts**, so it is unsuitable for daily use.

### Unsigned builds on Developer Edition / Nightly / ESR
Only these channels allow it: set `xpinstall.signatures.required` to `false` in `about:config`, then
install the unsigned `.xpi`. Not available on regular Firefox release.

## 2. Allow site access  **(verify)**

Firefox treats site access for Manifest V3 extensions as something you can grant or withhold.
After installing, open the Web2API popup: if a provider shows **Grant access**, click it and approve
the browser prompt. You can also check *about:addons → Web2API → Permissions*. A provider stays
disabled until access is granted.

## 3. Pair with the bridge

1. Click the Web2API toolbar icon (if hidden: the puzzle icon → pin it).
2. **Connection** → keep `ws://127.0.0.1:8787/ws/extension` (change only if you changed the port).
3. Paste the **pairing token** (`web2api-bridge pairing show`) → **Save & connect**. The pill should
   say **Connected**. (The `sk-w2a-…` API key is for your tools, not the popup.)

## 4. Log in and enable providers

Log in to chatgpt.com / claude.ai / gemini.google.com in this same Firefox profile (and any
containers: see below), then switch the providers on under **Providers** in the popup. Status meanings
are the same as in the [Chrome guide](install-chrome.md#4-enable-providers).

## 5. Firefox-specific behaviour

* **Containers.** If you use Multi-Account Containers, Web2API's worker tabs open in the **default
  container**. Log in to the providers in the default container (or use "Use current tab" from a
  tab in the container you prefer). **(verify: whether worker tabs can be assigned a container)**
* **Background pages.** Firefox may suspend idle background pages. Web2API keeps a lightweight
  heartbeat to the bridge; if the popup ever shows *Connecting…* for long, reload the extension or
  restart Firefox. **(verify during Phase 1)**
* **Pasting into the chat box.** Some sites rely on synthetic "paste" events that Firefox handles
  slightly differently; Web2API automatically falls back to other insertion methods. If a provider
  fails with `INPUT_REJECTED` only on Firefox, report it with a support bundle.
* **Worker window.** Same as Chrome: a small unfocused window holds the worker tabs; keep it visible
  (another desktop is fine) rather than minimised for best speed.
* Firefox must be running; otherwise API calls fail with `NO_EXTENSION` (HTTP 503).
* Private windows: extensions are off in private windows by default; leave Web2API that way.

## 6. Test it

Popup → **Test** → pick a provider → **Run**. Then follow the [quick start](quickstart.md).

## Updating and removing

* AMO installs update automatically; `.xpi` installs from the Releases page are signed with an update
  manifest so Firefox updates them too **(verify, depends on the chosen AMO channel)**.
* Remove: `about:addons` → Web2API → ⋯ → Remove.

## Troubleshooting (Firefox-specific)

| Symptom | Fix |
|---|---|
| "This add-on could not be installed because it appears to be corrupt" | The `.xpi` isn't signed for release Firefox. Use the AMO/signed file. |
| Extension vanished after restart | It was a temporary add-on. Install the signed `.xpi`. |
| Provider stuck at *Grant access* | Click it from the popup (needs a click, not automatic), or enable site access in `about:addons`. |
| *Bridge offline* | Start the bridge; check URL/port. |
| Works in Chrome but not Firefox | Generate a support bundle (`web2api-bridge support-bundle`) and the popup's *Copy diagnostics*; attach to an issue. |

More: [Troubleshooting](troubleshooting.md).
