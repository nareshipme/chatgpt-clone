import type { AuthResponse, FieldError } from "./types";

/** Error with the server's unified shape: { error: { code, message, details, requestId } }. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: FieldError[] | null = null,
    public requestId: string | null = null,
  ) {
    super(message);
  }
}

// The access token lives in memory only: it is never written to localStorage, so XSS cannot read a stored copy.
// The refresh token is an httpOnly cookie that JavaScript cannot see at all.
let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;

export const setAccessToken = (token: string | null) => {
  accessToken = token;
};
export const setSessionExpiredHandler = (fn: (() => void) | null) => {
  onSessionExpired = fn;
};

const BASE = "/api/v1";

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const e = body.error;
    return new ApiError(res.status, e.code, e.message, e.details ?? null, e.requestId ?? null);
  } catch {
    return new ApiError(res.status, "http_error", res.statusText || "Request failed");
  }
}

// Single-flight: concurrent callers (several 401s at once, React StrictMode's double effect) share ONE refresh call.
// Refresh tokens rotate and a replayed token revokes the session, so two parallel refreshes would log the user out.
let refreshInFlight: Promise<AuthResponse | null> | null = null;

export function refreshSession(): Promise<AuthResponse | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" });
        if (!res.ok) return null;
        const data = (await res.json()) as AuthResponse;
        accessToken = data.access_token;
        return data;
      } catch {
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Attach the access token and retry once after a silent refresh on 401. Default true. */
  auth?: boolean;
}

export async function api<T>(path: string, { method = "GET", body, auth = true }: RequestOptions = {}): Promise<T> {
  const send = () =>
    fetch(`${BASE}${path}`, {
      method,
      credentials: "same-origin",
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(auth && accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

  let res = await send();
  if (res.status === 401 && auth) {
    const refreshed = await refreshSession();
    if (refreshed) {
      res = await send();
    } else {
      accessToken = null;
      onSessionExpired?.();
    }
  }
  if (!res.ok) throw await parseError(res);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
