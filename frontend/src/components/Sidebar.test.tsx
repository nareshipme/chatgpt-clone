import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Conversation } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import ChatLayout from "../layout/ChatLayout";
import { ConversationPage, EmptyChatPage } from "../pages/ConversationPages";
import { calls, jsonResponse, stubFetch } from "../test/helpers";

const user = { id: "u1", email: "ada@example.com", display_name: "Ada", created_at: "" };
const session = { access_token: "tok", token_type: "bearer", user };

const conv = (id: string, title: string): Conversation => ({
  id,
  title,
  archived: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
});

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <Routes>
            <Route element={<ChatLayout />}>
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
  // jsdom has no matchMedia; report a desktop viewport so the permanent drawer renders.
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: true,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  })) as unknown as typeof window.matchMedia;
});

const refresh = { "POST /auth/refresh": () => jsonResponse(200, session) };

describe("conversations sidebar", () => {
  it("lists the user's conversations", async () => {
    stubFetch({
      ...refresh,
      "GET /conversations?limit=20": () => jsonResponse(200, { items: [conv("1", "Trip plan"), conv("2", "Budget")], next_cursor: null }),
    });
    renderAt("/");
    expect(await screen.findByText("Trip plan")).toBeInTheDocument();
    expect(screen.getByText("Budget")).toBeInTheDocument();
  });

  it("shows an empty state when there are no conversations", async () => {
    stubFetch({ ...refresh, "GET /conversations?limit=20": () => jsonResponse(200, { items: [], next_cursor: null }) });
    renderAt("/");
    expect(await screen.findByText(/no conversations yet/i)).toBeInTheDocument();
  });

  it("searches after a pause in typing and shows only the matches", async () => {
    const mock = stubFetch({
      ...refresh,
      "GET /conversations?limit=20": () => jsonResponse(200, { items: [conv("1", "Trip plan"), conv("2", "Budget")], next_cursor: null }),
      "GET /conversations?limit=20&q=budget": () => jsonResponse(200, { items: [conv("2", "Budget")], next_cursor: null }),
    });
    renderAt("/");
    await screen.findByText("Trip plan");
    await userEvent.type(screen.getByLabelText("Search conversations"), "budget");
    await waitFor(() => expect(screen.queryByText("Trip plan")).not.toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByText("Budget")).toBeInTheDocument();
    // debounced: one search request for the whole word, not one per keystroke
    expect(calls(mock, "GET /conversations?limit=20&q=budget")).toHaveLength(1);
    expect(mock.mock.calls.some(([u]) => String(u).includes("q=b&") || String(u).endsWith("q=b"))).toBe(false);
  });

  it("creates a new chat and opens it", async () => {
    let items: Conversation[] = [];
    stubFetch({
      ...refresh,
      "GET /conversations?limit=20": () => jsonResponse(200, { items, next_cursor: null }),
      "POST /conversations": () => {
        items = [conv("new-1", "New chat")];
        return jsonResponse(201, items[0]);
      },
      "GET /conversations/new-1": () => jsonResponse(200, conv("new-1", "New chat")),
    });
    renderAt("/");
    await userEvent.click(await screen.findByRole("button", { name: /new chat/i }));
    expect(await screen.findByRole("heading", { name: "New chat" })).toBeInTheDocument();
  });

  it("renames a conversation", async () => {
    const mock = stubFetch({
      ...refresh,
      "GET /conversations?limit=20": () => jsonResponse(200, { items: [conv("1", "Old title")], next_cursor: null }),
      "PATCH /conversations/1": () => jsonResponse(200, conv("1", "Better title")),
    });
    renderAt("/");
    await userEvent.click(await screen.findByRole("button", { name: /actions for old title/i }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Rename" }));
    const dialog = await screen.findByRole("dialog");
    const input = within(dialog).getByLabelText("Title");
    await userEvent.clear(input);
    await userEvent.type(input, "Better title");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls(mock, "PATCH /conversations/1")).toHaveLength(1));
    expect(JSON.parse(calls(mock, "PATCH /conversations/1")[0][1]!.body as string)).toEqual({ title: "Better title" });
  });

  it("asks for confirmation before deleting, then removes the conversation", async () => {
    let items = [conv("1", "Doomed"), conv("2", "Keeper")];
    const mock = stubFetch({
      ...refresh,
      "GET /conversations?limit=20": () => jsonResponse(200, { items, next_cursor: null }),
      "DELETE /conversations/1": () => {
        items = items.filter((c) => c.id !== "1");
        return jsonResponse(204);
      },
    });
    renderAt("/");
    await userEvent.click(await screen.findByRole("button", { name: /actions for doomed/i }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/permanently deleted/i)).toBeInTheDocument();
    expect(calls(mock, "DELETE /conversations/1")).toHaveLength(0); // nothing happens until confirmed
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByText("Doomed")).not.toBeInTheDocument());
    expect(screen.getByText("Keeper")).toBeInTheDocument();
  });

  it("loads the next page with the server cursor", async () => {
    const mock = stubFetch({
      ...refresh,
      "GET /conversations?limit=20": () => jsonResponse(200, { items: [conv("1", "First page item")], next_cursor: "cur-1" }),
      "GET /conversations?limit=20&cursor=cur-1": () => jsonResponse(200, { items: [conv("2", "Second page item")], next_cursor: null }),
    });
    renderAt("/");
    await screen.findByText("First page item");
    await userEvent.click(screen.getByRole("button", { name: /load more/i }));
    expect(await screen.findByText("Second page item")).toBeInTheDocument();
    expect(calls(mock, "GET /conversations?limit=20&cursor=cur-1")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument();
  });

  it("explains when a conversation does not exist or is not yours", async () => {
    stubFetch({
      ...refresh,
      "GET /conversations?limit=20": () => jsonResponse(200, { items: [], next_cursor: null }),
      "GET /conversations/nope": () =>
        jsonResponse(404, { error: { code: "conversation_not_found", message: "Conversation not found", details: null, requestId: "r" } }),
    });
    renderAt("/c/nope");
    expect(await screen.findByText(/does not exist or you do not have access/i)).toBeInTheDocument();
  });
});
