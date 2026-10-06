import { vi } from "vitest";

export function jsonResponse(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function errorBody(code: string, message: string, details: { field: string; message: string }[] | null = null) {
  return { error: { code, message, details, requestId: "req-1" } };
}

type Handler = (init?: RequestInit) => Response | Promise<Response>;

/** Stub global fetch with per-"METHOD /path" handlers (paths are relative to /api/v1). Returns the mock for assertions. */
export function stubFetch(handlers: Record<string, Handler>) {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input).replace("/api/v1", "");
    const key = `${init?.method ?? "GET"} ${url}`;
    const handler = handlers[key];
    if (!handler) throw new Error(`Unhandled fetch: ${key}`);
    return handler(init);
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

export const calls = (mock: ReturnType<typeof stubFetch>, key: string) =>
  mock.mock.calls.filter(([url, init]) => `${init?.method ?? "GET"} ${String(url).replace("/api/v1", "")}` === key);
