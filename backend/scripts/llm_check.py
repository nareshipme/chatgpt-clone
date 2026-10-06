"""Standalone check of the configured LLM. Reads LLM_API_KEY / LLM_BASE_URL / LLM_MODEL from the environment
(same names the app uses) and never prints the key.

    LLM_API_KEY=... [LLM_BASE_URL=...] [LLM_MODEL=...] python backend/scripts/llm_check.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

KEY = os.environ.get("LLM_API_KEY", "")
BASE = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "poolside/laguna-s-2.1:free")

if not KEY:
    sys.exit("LLM_API_KEY is not set")
print(f"base: {BASE}\nmodel: {MODEL}\nkey present: yes (length {len(KEY)})")

body = {"model": MODEL, "messages": [{"role": "user", "content": "Reply with exactly: hello from the test"}], "max_tokens": 40, "stream": True}
req = urllib.request.Request(
    f"{BASE}/chat/completions",
    data=json.dumps(body).encode(),
    method="POST",
    headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "User-Agent": "llm-check/1.0"},
)
start, text, chunks = time.time(), "", 0
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        for raw in r:
            line = raw.decode().strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                d = json.loads(line[6:])
                if d.get("choices"):
                    piece = d["choices"][0]["delta"].get("content") or ""
                    if piece:
                        chunks, text = chunks + 1, text + piece
except urllib.error.HTTPError as e:
    sys.exit(f"FAIL: HTTP {e.code} {e.read().decode()[:300]}")
print(f"{chunks} chunks in {time.time() - start:.1f}s -> {text!r}")
sys.exit(0 if text.strip() else "FAIL: empty reply")
