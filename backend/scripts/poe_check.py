"""Standalone Poe connectivity check. Reads POE_API_KEY from the environment; never prints it.

    POE_API_KEY=... python backend/scripts/poe_check.py [model]
"""
import json
import os
import sys
import urllib.error
import urllib.request

KEY = os.environ.get("POE_API_KEY", "")
MODEL = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("POE_MODEL", "claude-sonnet-5.5")


def call(method: str, url: str, body: dict | None = None) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body else None,
        method=method,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "User-Agent": "poe-check/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


if not KEY:
    sys.exit("POE_API_KEY is not set")
print(f"key present: yes (length {len(KEY)})")
s, b = call("GET", "https://api.poe.com/usage/current_balance")
print("balance:", s, b[:400])
s, b = call("GET", "https://api.poe.com/v1/models")
ids = [m["id"] for m in json.loads(b).get("data", [])] if s == 200 else []
print("models:", s, len(ids), "listed;", MODEL, "listed:", MODEL in ids)
s, b = call("POST", "https://api.poe.com/v1/chat/completions", {"model": MODEL, "messages": [{"role": "user", "content": "Say hi in 3 words."}], "max_tokens": 20})
print("chat:", s, b[:400])
