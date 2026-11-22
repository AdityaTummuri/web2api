#!/usr/bin/env python3
"""
web2api_keys.py - API key storage for the Web2API bridge.

Keys live in ``api.txt`` next to this file (override with ``WEB2API_KEYS_FILE``)
and/or the ``WEB2API_API_KEY`` environment variable. ``api.txt`` is generated
per install with cryptographically random keys and must never be committed.

CLI:
    python3 web2api_keys.py generate [--force]   # create api.txt with fresh keys
    python3 web2api_keys.py show                 # print the first usable key
"""

import argparse
import os
import re
import secrets
import stat
import sys
from typing import List, Optional

KEY_PATTERN = re.compile(r"\b(sk-w2a-[A-Za-z0-9_-]{16,})\b")

# Keys that were once committed to the public repository. They are treated as
# compromised and are never accepted, even if an old api.txt still contains them.
REVOKED_KEYS = frozenset(
    {
        "sk-w2a-dev-a7d4e1f9b3c820564917a2e8df3c9041",
        "sk-w2a-mobile-6c9b3e10fa4872159048a1b3df5e72c8",
        "sk-w2a-research-8e2b5c19fa7048361092a4f6de8a3b57",
        "sk-w2a-prod-3f1a9c40eb8275148902a7c5df6b81e4",
    }
)

KEY_LABELS = ("dev", "mobile", "research")


def keys_file_path() -> str:
    """Location of the key file (``WEB2API_KEYS_FILE`` or ``./api.txt``)."""
    override = os.getenv("WEB2API_KEYS_FILE")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "api.txt")


def load_keys() -> List[str]:
    """Return every accepted key (env var first, then api.txt), revoked keys removed."""
    keys: List[str] = []
    env_key = (os.getenv("WEB2API_API_KEY") or os.getenv("API_KEY") or "").strip()
    if env_key:
        keys.append(env_key)

    path = keys_file_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    for match in KEY_PATTERN.findall(line):
                        if match not in keys:
                            keys.append(match)
        except OSError:
            pass

    return [k for k in keys if k not in REVOKED_KEYS]


def default_key() -> Optional[str]:
    """First usable key, for local client scripts."""
    keys = load_keys()
    return keys[0] if keys else None


def new_key(label: str) -> str:
    return f"sk-w2a-{label}-{secrets.token_hex(24)}"


def generate_keys_file(path: Optional[str] = None, force: bool = False, port: int = 8000) -> str:
    """Write a fresh key file with owner-only permissions. Returns its path."""
    path = path or keys_file_path()
    if os.path.exists(path) and not force:
        raise FileExistsError(path)

    keys = {label: new_key(label) for label in KEY_LABELS}
    lines = [
        "=" * 80,
        "                 Web2API Bridge - API Credentials (KEEP PRIVATE)",
        "=" * 80,
        "Generated locally for this install. Do NOT commit or share this file.",
        "Regenerate any time with: python3 web2api_keys.py generate --force",
        "",
        f"OpenAI-compatible base URL (on this device): http://127.0.0.1:{port}/v1",
        "",
        "API KEYS (send as 'Authorization: Bearer <key>' or 'X-API-Key: <key>'):",
    ]
    for label, key in keys.items():
        lines.append(f"  {label:<9} {key}")
    lines += [
        "",
        "Browser extension bridge URL (paste into the extension popup):",
        f"  ws://127.0.0.1:{port}/ws?token={keys['dev']}",
        "",
    ]

    # Create with 0600 from the start so the keys are never world-readable.
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return path


def _has_only_revoked_keys(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            found = set(KEY_PATTERN.findall(fh.read()))
    except OSError:
        return False
    return not found or found <= REVOKED_KEYS


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Web2API API keys")
    sub = parser.add_subparsers(dest="cmd", required=True)
    gen = sub.add_parser("generate", help="Create api.txt with fresh random keys")
    gen.add_argument("--force", action="store_true", help="Overwrite an existing api.txt")
    gen.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    sub.add_parser("show", help="Print the first usable key")
    args = parser.parse_args(argv)

    if args.cmd == "generate":
        path = keys_file_path()
        force = args.force or (os.path.exists(path) and _has_only_revoked_keys(path))
        try:
            generate_keys_file(path, force=force, port=args.port)
        except FileExistsError:
            print(f"[keys] {path} already exists (use --force to replace it).")
            return 0
        print(f"[keys] Wrote fresh keys to {path} (permissions 600).")
        return 0

    key = default_key()
    if not key:
        print("[keys] No keys configured. Run: python3 web2api_keys.py generate", file=sys.stderr)
        return 1
    print(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
