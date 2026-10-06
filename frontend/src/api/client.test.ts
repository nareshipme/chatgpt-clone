import { beforeEach, describe, expect, it, vi } from "vitest";
import { calls, errorBody, jsonResponse, stubFetch } from "../test/helpers";

const authOk = { access_token: "new-token", token_type: "bearer", user: { id: "1", email: "a@x.com", display_name: "A", created_at: "" } };

// The client keeps module-level state (token, in-flight refresh), so load a fresh copy per test.
async function loadClient() {
  vi.resetModules();
  return await import("./client");
}

describe("api client", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("sends the access token as a Bearer header", async () => {
    const mock = stubFetch({ "GET /me": () => jsonResponse(200, { ok: true }) });
    const { api, setAccessToken } = await loadClient();
    setAccessToken("abc");
    await api("/me");
    const headers = mock.mock.calls[0][1]!.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer abc");
  });

  it("turns the server's unified error shape into an ApiError", async () => {
    stubFetch({ "POST /auth/login": () => jsonResponse(401, errorBody("invalid_credentials", "Invalid email or password")) });
    const { api, ApiError } = await loadClient();
    const err = await api("/auth/login", { method: "POST", body: {}, auth: false }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 401, code: "invalid_credentials", message: "Invalid email or password", requestId: "req-1" });
  });

  it("refreshes once on 401 and retries the original request with the new token", async () => {
    let first = true;
    const mock = stubFetch({
      "GET /me": () => {
        if (first) {
          first = false;
          return jsonResponse(401, errorBody("invalid_token", "expired"));
        }
        return jsonResponse(200, { ok: true });
      },
      "POST /auth/refresh": () => jsonResponse(200, authOk),
    });
    const { api, setAccessToken } = await loadClient();
    setAccessToken("old");
    await expect(api("/me")).resolves.toEqual({ ok: true });
    expect(calls(mock, "POST /auth/refresh")).toHaveLength(1);
    const retryHeaders = calls(mock, "GET /me")[1][1]!.headers as Record<string, string>;
    expect(retryHeaders.Authorization).toBe("Bearer new-token");
  });

  it("shares ONE refresh between concurrent 401s (a replayed refresh token would revoke the session)", async () => {
    const seen = new Set<string>();
    const mock = stubFetch({
      "GET /a": (init) => (seen.has("a") ? jsonResponse(200, "a") : (seen.add("a"), jsonResponse(401, errorBody("invalid_token", "x")))),
      "GET /b": (init) => (seen.has("b") ? jsonResponse(200, "b") : (seen.add("b"), jsonResponse(401, errorBody("invalid_token", "x")))),
      "POST /auth/refresh": async () => {
        await new Promise((r) => setTimeout(r, 20));
        return jsonResponse(200, authOk);
      },
    });
    const { api } = await loadClient();
    await Promise.all([api("/a"), api("/b")]);
    expect(calls(mock, "POST /auth/refresh")).toHaveLength(1);
  });

  it("clears the session and notifies the app when the refresh fails", async () => {
    stubFetch({
      "GET /me": () => jsonResponse(401, errorBody("invalid_token", "expired")),
      "POST /auth/refresh": () => jsonResponse(401, errorBody("invalid_refresh_token", "nope")),
    });
    const { api, setSessionExpiredHandler } = await loadClient();
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    await expect(api("/me")).rejects.toMatchObject({ status: 401 });
    expect(expired).toHaveBeenCalledOnce();
  });
});
