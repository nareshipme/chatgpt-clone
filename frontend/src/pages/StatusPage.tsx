import { useEffect, useRef, useState } from "react";

type Health = { status: string; db: string; redis: string };

// Deployment smoke test: API health and an SSE streaming check. Kept at /status as a diagnostic page.
export default function StatusPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ticks, setTicks] = useState<number[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch("/api/v1/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  async function testStream() {
    setTicks([]);
    setStreaming(true);
    abort.current = new AbortController();
    try {
      const res = await fetch("/api/v1/health/stream?ticks=8", { signal: abort.current.signal });
      const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += value;
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";
        for (const f of frames) {
          const m = f.match(/event: tick\ndata: (.*)/);
          if (m) setTicks((t) => [...t, JSON.parse(m[1]).n]);
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setStreaming(false);
    }
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 640, margin: "3rem auto", padding: "0 1rem" }}>
      <h1>BYond Chat</h1>
      <p>Deployment skeleton. If you can read this, the web service is up. (Deployed from GitHub via Railway autodeploy.)</p>
      <h2>API health</h2>
      {health ? <pre>{JSON.stringify(health, null, 2)}</pre> : <p>{error ?? "Checking..."}</p>}
      <h2>Streaming (SSE) test</h2>
      <button onClick={testStream} disabled={streaming}>
        {streaming ? "Streaming..." : "Start stream"}
      </button>
      <p>Ticks arrive one per second: {ticks.join(", ") || "none yet"}</p>
    </main>
  );
}
