"""Some open models write a tool call as text (``<tool_call>name<arg_key>k</arg_key><arg_value>v</arg_value></tool_call>``,
or Hermes-style ``<tool_call>{"name": ..., "arguments": {...}}</tool_call>``) instead of using the structured
tool-calls field. Left alone, that markup would appear in the chat and the tool would never run.

This filter sits on the text stream: it passes normal text straight through, holds back anything that could be the
start of a tool-call tag, and turns complete blocks into ToolCall objects.
"""
import json
import re

from app.llm.base import ToolCall

OPEN, CLOSE = "<tool_call>", "</tool_call>"
_PAIR = re.compile(r"<arg_key>(.*?)</arg_key>\s*<arg_value>(.*?)</arg_value>", re.S)


def _value(raw: str):
    raw = raw.strip()
    try:
        return json.loads(raw)  # numbers, booleans, null, quoted strings
    except ValueError:
        return raw


class ToolMarkupFilter:
    def __init__(self) -> None:
        self._buf = ""
        self._capturing = False
        self.calls: list[ToolCall] = []

    def feed(self, text: str) -> str:
        """Return the part of `text` that is safe to show now."""
        self._buf += text
        shown = ""
        while True:
            if self._capturing:
                end = self._buf.find(CLOSE)
                if end < 0:
                    return shown  # keep collecting
                self._parse(self._buf[:end])
                self._buf = self._buf[end + len(CLOSE) :]
                self._capturing = False
                continue
            start = self._buf.find(OPEN)
            if start >= 0:
                shown += self._buf[:start]
                self._buf = self._buf[start + len(OPEN) :]
                self._capturing = True
                continue
            # No full tag yet: hold back a trailing fragment that could still become one ("<tool_c").
            hold = next((n for n in range(min(len(OPEN) - 1, len(self._buf)), 0, -1) if OPEN.startswith(self._buf[-n:])), 0)
            shown += self._buf[: len(self._buf) - hold]
            self._buf = self._buf[len(self._buf) - hold :]
            return shown

    def flush(self) -> str:
        """The stream ended. An unfinished tool block is still parsed; leftover plain text is released."""
        if self._capturing:
            self._parse(self._buf)
            rest = ""
        else:
            rest = self._buf
        self._buf, self._capturing = "", False
        return rest

    def _parse(self, body: str) -> None:
        body = body.strip()
        if not body:
            return
        name, args = body, {}
        if body.startswith("{"):
            try:
                obj = json.loads(body)
                name, args = obj.get("name", ""), obj.get("arguments", obj.get("parameters", {}))
            except ValueError:
                return
        else:
            cut = body.find("<arg_key>")
            name = body if cut < 0 else body[:cut]
            args = {k.strip(): _value(v) for k, v in _PAIR.findall(body)}
        name = str(name).strip()
        if name:
            self.calls.append(ToolCall(f"call-text-{len(self.calls) + 1}", name, json.dumps(args if isinstance(args, dict) else {})))
