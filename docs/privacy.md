# Privacy

> Target-state document. This text is also the basis for the browser-store privacy policy
> (`spec/12-product-and-distribution.md` §9). Keep it accurate.

**Web2API collects no data and has no telemetry.** It has no servers of its own.

## What goes where

| Data | Where it goes |
|---|---|
| Your prompts | From your tool → the local bridge (your computer) → the extension → typed into the chat site in your browser. The chat site receives them exactly as if you typed them. |
| The answers | From the chat site (read by the extension from the page or from the site's own response) → bridge → your tool. |
| Your logins/cookies | Never read, copied or transmitted by Web2API. The browser keeps them; the site is accessed with your normal session. |
| API keys | Stored in `keys.json` as **hashes** only. |
| Pairing token | Stored in the bridge config folder and in the extension's local storage. |
| Settings, health reports | Local (extension storage and bridge folders). Health reports contain no prompt/answer text. |
| Page snapshots (for troubleshooting) | Local only, text content blanked (button labels kept), capped in number and size. Sent nowhere unless **you** attach them to an issue. |
| Logs | Local rotating files; prompts/answers excluded unless you enable content logging. |

## Network activity
* The bridge listens on `127.0.0.1` only. The extension talks only to the chat sites you enable and to
  `127.0.0.1`.
* The optional update check (`check_updates = true`, off by default) asks the project's release page
  for the latest version once a day and sends no identifiers.
* Nothing else.

## Your responsibilities
* Everything sent through Web2API is stored in the chat provider's history for your account (unless
  you use `history_mode = "temporary"` where supported) and is subject to the **provider's** privacy
  policy.
* Keep API keys private; revoke any you've exposed (`web2api-bridge keys revoke NAME`).

## Wiping everything
Remove the extension (deletes its storage), run `web2api-bridge service uninstall`, delete the
bridge's config and state folders (see [install](install-bridge.md#where-things-are-stored)), and
delete conversations in the chat sites themselves.
