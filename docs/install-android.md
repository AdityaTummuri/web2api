# Run Web2API on an Android phone

Turn a spare Android phone into a pocket Web2API server. The phone runs **both** the bridge
server (in Termux) and the logged-in browser (Firefox for Android + the Web2API extension).
Your laptop calls the API over **SSH** or **Tailscale**.

```
 Laptop (editor / SDK / curl)
      │  SSH tunnel  or  Tailscale
      ▼
 ┌─────────────────────── Android phone ───────────────────────┐
 │ Termux:  bridge_server.py  (127.0.0.1:8000)                  │
 │      ▲  ws://127.0.0.1:8000/ws?token=<key>                   │
 │ Firefox for Android + Web2API extension                      │
 │      └─► chatgpt.com / gemini.google.com / claude.ai tab     │
 └──────────────────────────────────────────────────────────────┘
```

## Requirements

| | Minimum | Notes |
|---|---|---|
| Android | 8.0+ | Android only; iOS is not supported (no Termux) |
| RAM | 3 GB | Keep **one** chat tab open |
| Storage | ~1 GB free | Termux + Python + Firefox |
| Power | Charger | The phone runs 24/7 with the screen able to sleep |
| Apps | Termux (F-Droid / GitHub), Firefox for Android, Tailscale *(optional)*, Termux:Boot *(optional)* | Do **not** use the Play Store build of Termux, it is outdated |

### Browser compatibility

| Browser | Status |
|---|---|
| Firefox for Android (120+) | ✅ Supported, recommended |
| Firefox Nightly / Beta for Android | ✅ Supported (easiest unsigned install) |
| Fennec F-Droid, Iceraven | Probably works (Firefox-based), untested |
| Chromium-based browsers with extension support | Best-effort only; Chromium is removing Manifest V2, which this extension uses |
| Chrome for Android | ❌ No extension support |

---

## 1. Install the server in Termux

```bash
pkg install -y git
git clone https://github.com/AdityaTummuri/web2api.git ~/web2api
cd ~/web2api
bash install.sh --with-ssh          # detects Termux automatically
# add --boot to start Web2API automatically when the phone boots (needs Termux:Boot)
```

What it does:
- installs Python with `pkg` (no Playwright, no headless browser)
- creates `.venv` and installs only `requirements-server.txt`
- generates **this phone's own random API keys** in `~/web2api/api.txt` (permissions 600, never committed)
- with `--with-ssh`, installs OpenSSH so your laptop can log in

> **`pydantic-core` (a compiled Rust package) is the only slow part.** On Termux with **Python 3.14 on
> ARM64** the installer downloads a prebuilt, checksum-verified copy from the
> [`android-wheels-v1` release](https://github.com/seeramsujay/web2api/releases/tag/android-wheels-v1),
> so the whole install takes about a minute. On other setups it compiles it instead. Measured on a
> Vivo Y91i (Android 8.1, 3 GB RAM): **~25 minutes**, plus ~650 MB of disk for Rust. While compiling
> it holds a wake lock and runs 2 parallel jobs (`WEB2API_BUILD_JOBS`), so Android doesn't kill Termux.
> Keep Termux open and the phone charging. The compiled wheel is kept in `.wheels/`, so reinstalls
> are fast. Set `WEB2API_PREBUILT=0` to always compile from source.

## 2. Start the server

Choose how your laptop will connect:

| Mode | Command | Exposure |
|---|---|---|
| **SSH** (default, most private) | `bash scripts/android/start-android.sh` | Listens on `127.0.0.1` only; the laptop uses an SSH tunnel |
| **Tailscale** | `WEB2API_MODE=tailscale bash scripts/android/start-android.sh` | Listens on `127.0.0.1` + the phone's Tailscale IP only (not on Wi-Fi/LAN); **API key always required** |

The script grabs a wake lock (so Android doesn't suspend it) and prints the exact bridge URL and laptop
command you need.

> The server refuses to listen on a network address unless API keys exist. That is on purpose:
> without a key, anyone on the same Wi-Fi could use your logged-in chat accounts.

## 3. Install the extension in Firefox for Android

Firefox for Android only installs **signed** extensions, except on Nightly/Beta. Pick one route.
Regular Firefox **silently ignores** an unsigned `.xpi`, so if Web2API doesn't appear under Extensions,
you're probably on regular Firefox: use route A or B.

**A. Signed `.xpi` (works on regular Firefox, recommended for everyone)**

1. On your laptop, create a free account at addons.mozilla.org and generate API credentials
   (*Developer Hub → Manage API Keys*).
2. Build and sign as an **unlisted** add-on (it isn't published in the store):
   ```bash
   cd extension
   npm run build
   WEB_EXT_API_KEY=<jwt issuer> WEB_EXT_API_SECRET=<jwt secret> npm run sign:android
   ```
   The signed file lands in `extension/dist/signed/`.
3. Copy the `.xpi` to the phone. In Firefox go to *Settings → About Firefox* and tap the logo
   5 times to enable the debug menu. Then use *Settings → Install extension from file*.
   If the `.xpi` is **greyed out** in the file picker (common on Android), install it from a link
   instead: in Termux `cd ~/web2api/extension && python -m http.server 8002 --bind 127.0.0.1`, then
   open `http://127.0.0.1:8002/<file>.xpi` in Firefox and tap **Add**.

**B. Firefox Nightly (no signing)**: open `about:config`, set `xpinstall.signatures.required` to
`false`, then install the unsigned `extension/web2api-firefox.xpi` from *Install extension from file*.

**C. Development (temporary, over USB)**: enable USB debugging on the phone, then on the laptop:
```bash
cd extension && npm run build && npm run run:android -- --android-device=<adb device id>
```

### Pair the extension with the server

1. In Firefox, open the menu → *Extensions* → **Web2API** to open the popup.
2. **Pair with a 6-digit code** (no long key to copy): in Termux run
   `python web2api_keys.py pair` (inside `~/web2api`). Type the 6-digit code into the popup's
   **Bridge URL** box and tap **Connect**. The code works once, only from the phone itself, and
   expires after 10 minutes.
   *(Alternatives: paste a full `ws://127.0.0.1:8000/ws?token=<key>` URL, or run
   `bash scripts/android/show-bridge-url.sh` and open http://127.0.0.1:8001 to copy it.)*
3. In the same Firefox, log in to the chat site you want to use (ChatGPT, Gemini or Claude) and
   **leave that tab open**.

## 4. Connect from your laptop

### Option 1: SSH tunnel (default mode)

Set up a key once:

```bash
# in Termux on the phone
whoami            # e.g. u0_a123  -> your SSH user
passwd            # temporary password, used only for the next step
sshd              # start the SSH server (port 8022)

# on the laptop
ssh-keygen -t ed25519                      # skip if you already have a key
ssh-copy-id -p 8022 u0_a123@<phone-ip>     # phone-ip: LAN IP or Tailscale IP/name
```

Optional hardening: in Termux, set `PasswordAuthentication no` in `$PREFIX/etc/ssh/sshd_config`,
then restart with `pkill sshd; sshd`.

Then each time:

```bash
scripts/android/connect-from-laptop.sh <phone-ip> u0_a123
# or by hand:  ssh -N -p 8022 -L 8000:127.0.0.1:8000 u0_a123@<phone-ip>
```

Your tools use `http://127.0.0.1:8000/v1` as if the server were local.

### Option 2: Tailscale

1. Install Tailscale on the phone (Play Store or F-Droid) and the laptop. Sign in to the **same**
   account on both.
2. Start the server with `WEB2API_MODE=tailscale`. It prints the phone's `100.x.y.z` address.
3. From the laptop: `http://<phone-tailscale-ip-or-name>:8000/v1`.

Tailscale and SSH combine well: run SSH mode and point `connect-from-laptop.sh` at the phone's
Tailscale name. That works from anywhere with zero ports exposed.

### Get your API key on the laptop

```bash
ssh -p 8022 u0_a123@<phone-ip> 'cd ~/web2api && .venv/bin/python web2api_keys.py show'
```

### Call it

```bash
export WEB2API_KEY=sk-w2a-dev-...
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $WEB2API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"chatgpt","messages":[{"role":"user","content":"Reply with exactly: PONG"}]}'
```

Any OpenAI SDK works with `base_url=http://127.0.0.1:8000/v1` (or the Tailscale URL) and
`api_key=$WEB2API_KEY`.

## 5. Keep it alive (important on Android)

Android aggressively kills background apps. Do all of these:

- **Battery optimisation off** for *Termux*, *Firefox* and *Tailscale*
  (Settings → Apps → *app* → Battery → *Unrestricted* / *Don't optimise*).
- Keep the phone **on the charger**. Optionally enable *Developer options → Stay awake while charging*.
- Keep **Firefox in the foreground** with the chat tab visible. Background tabs get frozen or
  discarded, and then prompts time out.
- Keep the Termux notification (wake lock). `start-android.sh` acquires it for you.
- On Xiaomi, Samsung, Oppo, Huawei and similar phones, also follow the vendor-specific steps on
  dontkillmyapp.com.

### Tips for 3 GB phones
- Use **one** provider tab. Every extra chat tab costs hundreds of MB.
- Close other apps and turn off Firefox features you don't need (e.g. extra tabs, sync).
- `bash scripts/android/doctor.sh` warns when free memory drops below 400 MB.

## 6. Auto-start on boot (optional)

Install the **Termux:Boot** app (from the same source as Termux), open it once, then run
`bash install.sh --boot` (or `bash scripts/android/install-termux.sh --boot`).
The server starts on boot and logs to `~/web2api.log`. You still need to open Firefox yourself.

## Health check

```bash
bash scripts/android/doctor.sh
```
Checks dependencies, keys, the server, the extension connection, auth enforcement, sshd and
free memory.

## Status and known issues (tested on a real phone)

Tested end to end on a Vivo Y91i (Android 8.1, 3 GB RAM) with Termux, Firefox Nightly and Tailscale.

| Part | Status |
|---|---|
| Install (prebuilt wheel) | ✅ ~2 min fresh, <1 min reinstall |
| Server, auth, SSH and Tailscale modes | ✅ 56 MB RAM, 0.1–0.25 s bridge overhead, survives screen-off |
| Extension install + pairing code | ✅ Firefox Nightly, extension 2.0.6 |
| ChatGPT: type and send the prompt | ✅ ChatGPT receives and answers it |
| ChatGPT: read the reply back | ❌ **Not working yet on mobile ChatGPT.** The reply isn't in the page DOM the extension sees (only the header and composer). 2.0.6 adds iframe/shadow-DOM search and diagnostics to investigate |
| Gemini / Claude on mobile | Not tested yet |

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pip` fails building `pydantic-core` | Re-run the installer; it compiles with the Termux `maturin` package. Lower memory use with `WEB2API_BUILD_JOBS=1` |
| Termux/SSH disappears during install | Android killed Termux (low memory or battery manager). Allow Termux background activity, keep it in the foreground, re-run the installer; finished parts are skipped |
| `… android_27_arm64_v8a.whl is not a supported wheel` | Wheel tagged with the phone's API level instead of Termux Python's (24). Fixed in the installer; pull the latest branch and re-run |
| `Refusing to listen on 0.0.0.0 without an API key` | Run `python web2api_keys.py generate`, or use SSH mode |
| `503 Browser Extension is not connected` | Open Firefox; check the popup bridge URL includes `?token=<key>`; tap Connect |
| `401 Unauthorized` | Send `Authorization: Bearer <key>` with a key from the phone's `api.txt` |
| Requests time out | Firefox was backgrounded or the tab was discarded. Bring it to the front; disable battery optimisation |
| Server dies when the screen turns off | Battery optimisation is still on for Termux, or the wake lock was released |
| `ssh: connect to host … port 8022: Connection refused` | Run `sshd` in Termux (SSH mode starts it automatically) |
| Rotate keys | `python web2api_keys.py generate --force`, restart the server, paste the new bridge URL |
