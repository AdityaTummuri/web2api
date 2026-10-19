# Releasing

Runbook for cutting a release (1.0.0, 2.0.0, and every release after). Pipeline design:
`spec/12-product-and-distribution.md` §8. **A release is public and hard to retract — never publish
one whose acceptance criteria aren't met.** Pre-release tags (`v2.0.0-rc.1`) are for testing the
pipeline and may be published as GitHub *pre-releases*.

## 0. Preconditions

| Release | Must be true |
|---|---|
| 1.0.0 | `spec/12` §11 "Definition of done for 1.0" fully ticked. |
| 2.0.0 | 1.0.0 released; `spec/10` Phase 10 acceptance criteria pass; MCP client matrix filled in `docs/compatibility.md`. |
| any | CI green on `master`; `CHANGELOG.md` has an entry for the version; docs match behaviour (no "target-state" banners left that are now false). |

Owner decisions that gate 1.0.0 (record in `spec/OPEN_QUESTIONS.md`): license, macOS/Windows signing,
Chrome Web Store + AMO accounts, final project name.

## 1. Version bump (one commit)

Update, in the same commit `chore(release): vX.Y.Z`:
1. `bridge/pyproject.toml` `version` and `web2api_bridge/__init__.py` `__version__`.
2. `extension/manifests/base.json` `version` (stores need `a.b.c`; for `-rc` builds use `a.b.c` plus the
   store's pre-release channel, or keep the numeric part only).
3. `CHANGELOG.md`: rename *Planned/Unreleased* items into `## [X.Y.Z] - YYYY-MM-DD`, add compare links.
4. `minPeerVersion` values (protocol handshake, `spec/12` §7) if the compatibility floor changed.
5. Compatibility matrix table in `README.md`.

## 2. Verify locally

```bash
cd extension && npm ci && npm test && npm run build
cd ../bridge && uv sync --frozen && uv run pytest && uv run pytest tests/conformance   # needs `uv run --with openai` for the SDK suite
# v2.0.0 additionally:
uv run --with mcp pytest tests/mcp_conformance
web2api-bridge doctor --probe          # with the extension loaded and real providers logged in
bridge/scripts/smoke.py chatgpt claude gemini      # live smoke (spec/09 §4.1), 3 consecutive passes
```

## 3. Tag and let CI build

```bash
git switch master && git pull --ff-only
git tag -s vX.Y.Z -m "Web2API vX.Y.Z"      # signed tag if you have a signing key, else -a
git push origin master vX.Y.Z
```
The tag-triggered workflow (`spec/12` §8) then: builds binaries on the five native runners, runs the full
integration (+ MCP in 2.0.0) suite **against each binary**, checks size/startup/RSS budgets, builds
Chrome/Firefox zips (+ `web-ext lint`), builds wheel/sdist, publishes to PyPI via trusted publishing,
generates and signs `SHA256SUMS`, and creates a **draft** GitHub release with all assets and the
`CHANGELOG.md` section as notes.

## 4. Review the draft, then publish

1. Download one asset per OS; verify `SHA256SUMS` and the signature as a user would.
2. Run the binary: `--version`, `doctor`, a real chat call.
3. Publish the draft (`gh release edit vX.Y.Z --draft=false`) — or `--prerelease` for `-rc` tags.

## 5. Extensions (manual gate)

* **Chrome Web Store:** upload `web2api-extension-X.Y.Z-chrome.zip` in the developer dashboard, paste
  the listing text from `docs/store/` (permission justifications, privacy policy link), submit; review
  can take days. Keep the same extension id (manifest `key`).
* **Firefox AMO:** upload the Firefox zip (listed or unlisted channel) for signing; attach the source
  archive and build steps if requested (`npm ci && npm run build:firefox` — no minification, so review is
  simple). Publish the signed `.xpi` as a release asset too.
* Compatibility: the extension and bridge version floors (`minPeerVersion`) must match what the store
  versions can talk to; don't roll out a bridge that requires an extension version still in review
  (publish the extension first, bridge second, when the floor rises).

## 6. After publishing

1. Update `docs/providers.md` "last verified" dates from the live smoke run.
2. Announce (README badge, issue/discussion post) with the notes and any known limitations.
3. Open a milestone for the next version; move deferred items there.

## 7. Hotfixes and rollbacks

* **Provider breakage** (site changed): ship a **config override** (hot, no release; `spec/05` §2.4) and
  fold it into the bundled config in a patch release `X.Y.(Z+1)`.
* **Bad release:** yank the PyPI version (`pip`-style yank, not delete), mark the GitHub release
  *pre-release* with a warning banner, publish the fix as the next patch; never rewrite tags.
* Store rollbacks: re-submit the previous good zip with a higher version number (stores don't allow
  downgrades).

## 8. Release checklist (copy into the release issue)

- [ ] Preconditions met (§0)  - [ ] Version bump commit (§1)  - [ ] Local verification (§2)
- [ ] Tag pushed, CI green (§3)  - [ ] Draft assets verified on 3 OSes (§4)  - [ ] Published
- [ ] Chrome Web Store submitted  - [ ] AMO submitted/signed (§5)
- [ ] Docs/providers table updated  - [ ] Announcement  - [ ] Next milestone created (§6)
