import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Conversation } from "../api/types";
import ChatLayout from "../layout/ChatLayout";
import LoginPage from "../pages/LoginPage";
import { ConversationPage, EmptyChatPage } from "../pages/ConversationPages";
import { AuthProvider } from "./AuthContext";
import { PublicOnly, RequireAuth } from "./RequireAuth";
import { jsonResponse, stubFetch } from "../test/helpers";

const person = (id: string, name: string) => ({ id, email: `${name}@example.com`, display_name: name, created_at: "" });
const conv = (id: string, title: string): Conversation => ({
  id, title, archived: false, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
});

function renderApp(start = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[start]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
            <Route element={<RequireAuth><ChatLayout /></RequireAuth>}>
              <Route path="/" element={<EmptyChatPage />} />
              <Route path="/c/:conversationId" element={<ConversationPage />} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetModules();
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: true, media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
  })) as unknown as typeof window.matchMedia;
});

describe("switching accounts in the same tab", () => {
  it("never shows the previous user's conversations to the next user", async () => {
    let current: "alice" | "bob" = "alice";
    const lists = { alice: [conv("a1", "Alice private chat")], bob: [conv("b1", "Bob's chat")] };
    stubFetch({
      "POST /auth/refresh": () => jsonResponse(200, { access_token: "ta", token_type: "bearer", user: person("ua", "Alice") }),
      "POST /auth/logout": () => new Response(null, { status: 204 }),
      "POST /auth/login": () => {
        current = "bob";
        return jsonResponse(200, { access_token: "tb", token_type: "bearer", user: person("ub", "Bob") });
      },
      // Bob's list answers slowly, which is exactly when stale data from Alice would be visible.
      "GET /conversations?limit=20": async () => {
        if (current === "bob") await new Promise((r) => setTimeout(r, 150));
        return jsonResponse(200, { items: lists[current], next_cursor: null });
      },
    });

    renderApp();
    expect(await screen.findByText("Alice private chat")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    await userEvent.type(await screen.findByLabelText(/email/i), "bob@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "bobs-long-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/hello, bob/i);
    // While Bob's list is still loading, Alice's data must already be gone from the screen.
    expect(screen.queryByText("Alice private chat")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Bob's chat")).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.queryByText("Alice private chat")).not.toBeInTheDocument();
  });

  it("does not send the next user to the previous user's page after an explicit sign-out", async () => {
    let signedIn = "alice";
    stubFetch({
      "POST /auth/refresh": () => jsonResponse(200, { access_token: "ta", token_type: "bearer", user: person("ua", "Alice") }),
      "POST /auth/logout": () => new Response(null, { status: 204 }),
      "POST /auth/login": () => {
        signedIn = "bob";
        return jsonResponse(200, { access_token: "tb", token_type: "bearer", user: person("ub", "Bob") });
      },
      "GET /conversations?limit=20": () => jsonResponse(200, { items: [], next_cursor: null }),
      "GET /conversations/a1": () =>
        signedIn === "alice"
          ? jsonResponse(200, conv("a1", "Alice private chat"))
          : jsonResponse(404, { error: { code: "conversation_not_found", message: "Conversation not found", details: null, requestId: "r" } }),
    });

    renderApp("/c/a1"); // Alice is looking at one of her conversations
    expect(await screen.findByRole("heading", { name: "Alice private chat" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    await userEvent.type(await screen.findByLabelText(/email/i), "bob@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "bobs-long-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    // Bob lands on his own home screen, not on Alice's conversation URL.
    expect(await screen.findByText(/hello, bob/i)).toBeInTheDocument();
    expect(screen.queryByText(/does not exist or you do not have access/i)).not.toBeInTheDocument();
  });
});
