export interface SseFrame {
  event: string;
  data: unknown;
}

/** Parse one SSE block ("event: x" + "data: {...}" lines). Comment lines (": ping") are ignored. */
function parseBlock(block: string): SseFrame | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue; // heartbeat / comment
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  if (data.length === 0) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) };
  } catch {
    return null; // a malformed frame must not kill the whole stream
  }
}

/**
 * Read a Server-Sent Events body and yield frames as they arrive.
 * Network chunks do not respect frame boundaries, so we buffer until a blank line ends a frame.
 * Closing the generator (or aborting the fetch) cancels the underlying reader.
 */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseFrame> {
  const reader = body.getReader();
  // stream: true keeps a multi-byte character that is split across two chunks intact.
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const frame = parseBlock(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
        if (frame) yield frame;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
  }
}
