import { describe, expect, it } from "vitest";
import { readSse, type SseFrame } from "./sse";

/** A body that emits the given string chunks, exactly as the network might split them. */
function bodyOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
}

async function collect(chunks: string[]): Promise<SseFrame[]> {
  const out: SseFrame[] = [];
  for await (const f of readSse(bodyOf(chunks))) out.push(f);
  return out;
}

describe("readSse", () => {
  it("parses events and JSON data", async () => {
    const frames = await collect(['event: token\ndata: {"text":"Hi"}\n\n', 'event: done\ndata: {"ok":true}\n\n']);
    expect(frames).toEqual([
      { event: "token", data: { text: "Hi" } },
      { event: "done", data: { ok: true } },
    ]);
  });

  it("reassembles a frame split across network chunks, even mid-word", async () => {
    const frames = await collect(['event: tok', 'en\ndata: {"te', 'xt":"Hel', 'lo"}\n', "\n"]);
    expect(frames).toEqual([{ event: "token", data: { text: "Hello" } }]);
  });

  it("handles several frames in one chunk", async () => {
    const frames = await collect(['event: token\ndata: {"text":"a"}\n\nevent: token\ndata: {"text":"b"}\n\n']);
    expect(frames.map((f) => (f.data as { text: string }).text)).toEqual(["a", "b"]);
  });

  it("ignores heartbeat comments", async () => {
    const frames = await collect([': ping\n\n', 'event: token\ndata: {"text":"x"}\n\n', ": ping\n\n"]);
    expect(frames).toEqual([{ event: "token", data: { text: "x" } }]);
  });

  it("accepts CRLF line endings", async () => {
    const frames = await collect(['event: token\r\ndata: {"text":"x"}\r\n\r\n']);
    expect(frames).toEqual([{ event: "token", data: { text: "x" } }]);
  });

  it("skips a malformed frame without breaking the stream", async () => {
    const frames = await collect(["event: token\ndata: {not json}\n\n", 'event: token\ndata: {"text":"ok"}\n\n']);
    expect(frames).toEqual([{ event: "token", data: { text: "ok" } }]);
  });

  it("drops an incomplete trailing frame (the connection ended mid-frame)", async () => {
    const frames = await collect(['event: token\ndata: {"text":"a"}\n\n', 'event: token\ndata: {"text":"cut']);
    expect(frames).toHaveLength(1);
  });

  it("stops reading when the consumer stops early", async () => {
    let cancelled = false;
    const enc = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      pull(controller) {
        controller.enqueue(enc.encode('event: token\ndata: {"text":"x"}\n\n'));
      },
      cancel() {
        cancelled = true;
      },
    });
    for await (const _ of readSse(body)) break; // user pressed Stop after the first token
    expect(cancelled).toBe(true);
  });
});
