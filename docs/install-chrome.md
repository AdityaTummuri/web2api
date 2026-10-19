# Install on Chrome (and Edge, Brave, Chromium, Vivaldi, Opera)

> Target-state guide (see README status note). Requires Chrome/Chromium **116 or newer** — check at
> `chrome://version`.

Before you start, [install and start the bridge](install-bridge.md) and keep its **pairing token** handy.

## 1. Install the extension

### From the Chrome Web Store (recommended, once published)
Open the Web2API listing → **Add to Chrome**. Updates install automatically. Edge, Brave, Vivaldi and
Opera can install Chrome Web Store extensions too.

### Manually (development builds or before the store listing exists)
1. Get the build: download `web2api-extension-<version>-chrome.zip` from the Releases page and unzip it
   to a folder you will keep (Chrome loads it from there), **or** build it yourself:
   ```bash
   cd extension && npm ci && npm run build:chrome     # output: extension/dist/chrome
   ```
2. Open `chrome://extensions` (Edge: `edge://extensions`, Brave: `brave://extensions`).
3. Turn on **Developer mode** (top right).
4. Click **Load unpacked** and select the folder (the one containing `manifest.json`).
5. Click the puzzle-piece icon in the toolbar and **pin** Web2API so you can see its status.

> Chrome may show a "Disable developer mode extensions" banner at startup for manual installs and does
> not auto-update them. The Web Store install avoids both.

## 2. Pair with the bridge

1. Click the Web2API icon → **Connection**.
2. Leave the bridge URL as `ws://127.0.0.1:8787/ws/extension` (change it only if you changed the port).
3. Paste the **pairing token** (`web2api-bridge pairing show`) → **Save & connect**.
4. The status pill should turn **Connected**. If it says *Pairing token rejected*, you pasted the wrong
   token (don't paste the `sk-w2a-…` API key here — that's for your tools).

## 3. Log in to the chat sites

In the **same Chrome profile**, open and log in to the sites you want to use (chatgpt.com, claude.ai,
gemini.google.com). Solve any "verify you are human" prompts once yourself.

## 4. Enable providers

In the popup → **Providers**: switch on the providers you use. Chrome asks you to allow access to each
site — approve it. A provider shows:

| Status | Meaning |
|---|---|
| Ready | A worker tab is open and logged in |
| No tabs | Fine — Web2API opens a worker tab when the first request arrives |
| Login required | Log in to that site in this Chrome profile |
| Degraded / Unhealthy | The site changed; see [Troubleshooting](troubleshooting.md) |

## 5. How it behaves in Chrome

* Web2API opens its own small **worker window** (not focused) for the chat tabs. You can minimise or
  move it, but a fully minimised window may make some sites update slowly — if answers are slow, leave
  the window visible on another desktop/monitor. (Setting *Worker window mode* in the popup; the
  default is the dedicated window.)
* It **never** types into tabs you opened yourself, unless you click **Use current tab** for that
  provider in the popup.
* You can keep using Chrome normally. Closing the worker window just makes Web2API open a new one on
  the next request.
* Chrome must be running. If Chrome is closed, API calls fail with `NO_EXTENSION` (HTTP 503).

## 6. Test it

Popup → **Test** → choose a provider → type a prompt → **Run**. You should see the answer stream in.
Then try the [quick start](quickstart.md) with curl.

## Updating and removing

* Store installs update themselves. Manual installs: download the new zip, replace the folder contents,
  then click the reload icon on the extension's card in `chrome://extensions`.
* Remove: `chrome://extensions` → Remove. Your pairing token and settings are deleted with it.

## Troubleshooting (Chrome-specific)

| Symptom | Fix |
|---|---|
| Popup says *Bridge offline* | Start the bridge (`web2api-bridge`); check the URL/port in the popup. |
| *Version mismatch* | Update the bridge or the extension to compatible versions (see release notes). |
| Extension disappears at restart | You loaded it unpacked from a folder that moved/was deleted. Keep the folder, or use the Web Store build. |
| Provider stays *Login required* though you're logged in | You're logged in under a different Chrome profile. Use the profile where the extension is installed. |
| Slow answers when the worker window is minimised | Un-minimise it or move it to another desktop (browsers throttle hidden pages). |

More: [Troubleshooting](troubleshooting.md).
