import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Conversation, Message } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import ChatLayout from "../layout/ChatLayout";
import { calls, errorBody, jsonResponse, stubFetch } from "../test/helpers";
import { ConversationPage, EmptyChatPage } from "./ConversationPages";

const user = { id: "u1", email: "ada@example.com", display_name: "Ada", created_at: "" };
const session = { access_token: "tok", token_type: "bearer", user };
const conversation: Conversation = { id: "c1", title: "Trip plan", archived: false, created_at: "", updated_at: "" };

const msg = (id: string, role: Message["role"], text: string, status: Message["status"] = "complete"): Message => ({
  id, conversation_id: "c1", role, status, created_at: "", parts: [{ type: "text", text }],
});

/** A server-sent-events response the test controls: push frames one at a time, then close. */
function sseResponse(init?: RequestInit) {
  let ctrl!: ReadableStreamDefaultController<Uint8Array>;
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({ start: (c) => (ctrl = c) });
  // Like a real fetch, an abort makes the pending read fail with AbortError.
  init?.signal?.addEventListener("abort", () => ctrl.error(new DOMException("aborted", "AbortError")));
  return {
    response: new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } }),
    push: (event: string, data: object) => ctrl.enqueue(enc.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)),
    close: () => ctrl.close(),
  };
}

function setup(opts: { history?: Message[]; onSend?: (init?: RequestInit) => Response | Promise<Response> } = {}) {
  let thread = opts.history ?? [];
  const mock = stubFetch({
    "POST /auth/refresh": () => jsonResponse(200, session),
    "GET /conversations?limit=20": () => jsonResponse(200, { items: [conversation], next_cursor: null }),
    "GET /conversations/c1": () => jsonResponse(200, conversation),
    "GET /conversations/c1/messages": () => jsonResponse(200, { items: thread }),
    "POST /conversations/c1/messages": (init) => opts.onSend!(init),
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/c/c1"]}>
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
  return { mock, setThread: (m: Message[]) => (thread = m) };
}

beforeEach(() => {
  vi.resetModules();
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: true, media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
  })) as unknown as typeof window.matchMedia;
  Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo; // jsdom has no scrollTo
});

const box = () => screen.findByLabelText("Message");

describe("chat", () => {
  it("shows the saved conversation history", async () => {
    setup({ history: [msg("m1", "user", "Where should I go?"), msg("m2", "assistant", "Lisbon is lovely.")] });
    expect(await screen.findByText("Where should I go?")).toBeInTheDocument();
    expect(screen.getByText("Lisbon is lovely.")).toBeInTheDocument();
  });

  it("shows an empty-thread hint", async () => {
    setup();
    expect(await screen.findByText(/send a message to start the conversation/i)).toBeInTheDocument();
  });

  it("keeps Send disabled until there is non-blank text", async () => {
    setup();
    const send = await screen.findByRole("button", { name: "Send message" });
    expect(send).toBeDisabled();
    await userEvent.type(await box(), "   ");
    expect(send).toBeDisabled();
    await userEvent.type(await box(), "hi");
    expect(send).toBeEnabled();
  });

  it("streams the reply token by token, offers Stop meanwhile, then shows the saved messages", async () => {
    let sse!: ReturnType<typeof sseResponse>;
    const { mock, setThread } = setup({ onSend: (init) => (sse = sseResponse(init)).response });
    await userEvent.type(await box(), "Say hello");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));

    // The user's message appears at once and Stop replaces Send.
    expect(await screen.findByText("Say hello")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Stop generating" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send message" })).not.toBeInTheDocument();

    sse.push("start", { assistant_message_id: "m2" });
    sse.push("token", { text: "Hel" });
    expect(await screen.findByText(/^Hel/)).toBeInTheDocument();
    sse.push("token", { text: "lo!" });
    expect(await screen.findByText(/^Hello!/)).toBeInTheDocument();

    // The server saves the turn; on done the client replaces the live text with the stored messages.
    setThread([msg("m1", "user", "Say hello"), msg("m2", "assistant", "Hello!")]);
    sse.push("done", { message_id: "m2" });
    sse.close();
    await waitFor(() => expect(screen.getByRole("button", { name: "Send message" })).toBeInTheDocument());
    expect(screen.getAllByText("Hello!")).toHaveLength(1); // not duplicated (live copy replaced by the saved one)
    expect(screen.getAllByText("Say hello")).toHaveLength(1);
    expect(calls(mock, "POST /conversations/c1/messages")).toHaveLength(1);
    expect(JSON.parse(calls(mock, "POST /conversations/c1/messages")[0][1]!.body as string)).toEqual({ content: "Say hello" });
    // sidebar list and title are refreshed after a turn
    expect(calls(mock, "GET /conversations?limit=20").length).toBeGreaterThanOrEqual(2);
  });

  it("sends on Enter but not on Shift+Enter", async () => {
    let sse!: ReturnType<typeof sseResponse>;
    const { mock } = setup({ onSend: (init) => (sse = sseResponse(init)).response });
    const input = await box();
    await userEvent.type(input, "line one{Shift>}{Enter}{/Shift}line two");
    expect(calls(mock, "POST /conversations/c1/messages")).toHaveLength(0);
    expect((input as HTMLTextAreaElement).value).toBe("line one\nline two");
    await userEvent.type(input, "{Enter}");
    await waitFor(() => expect(calls(mock, "POST /conversations/c1/messages")).toHaveLength(1));
    expect(JSON.parse(calls(mock, "POST /conversations/c1/messages")[0][1]!.body as string)).toEqual({ content: "line one\nline two" });
    sse.close();
  });

  it("clears the box after sending", async () => {
    let sse!: ReturnType<typeof sseResponse>;
    setup({ onSend: (init) => (sse = sseResponse(init)).response });
    const input = (await box()) as HTMLTextAreaElement;
    await userEvent.type(input, "hello");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(input.value).toBe(""));
    sse.close();
  });

  it("Stop aborts the request, and the partial reply is kept as 'Stopped'", async () => {
    let sse!: ReturnType<typeof sseResponse>;
    let signal: AbortSignal | undefined;
    const { setThread } = setup({ onSend: (init) => ((signal = init?.signal ?? undefined), (sse = sseResponse(init)).response) });
    await userEvent.type(await box(), "Tell me a story");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    sse.push("token", { text: "Once upon" });
    await screen.findByText(/^Once upon/);

    setThread([msg("m1", "user", "Tell me a story"), msg("m2", "assistant", "Once upon", "interrupted")]);
    await userEvent.click(screen.getByRole("button", { name: "Stop generating" }));
    expect(signal?.aborted).toBe(true);
    expect(await screen.findByText("Stopped", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText("Once upon")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Send message" })).toBeInTheDocument());
  });

  it("shows an in-stream error and keeps the text that had arrived", async () => {
    let sse!: ReturnType<typeof sseResponse>;
    const { setThread } = setup({ onSend: (init) => (sse = sseResponse(init)).response });
    await userEvent.type(await box(), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    sse.push("token", { text: "Partial " });
    await screen.findByText(/^Partial/);
    setThread([msg("m1", "user", "hello"), msg("m2", "assistant", "Partial answer", "error")]);
    sse.push("error", { code: "llm_unavailable", message: "The assistant is unavailable right now." });
    sse.close();
    expect(await screen.findByText("The assistant is unavailable right now.")).toBeInTheDocument();
    expect(await screen.findByText("This reply did not finish")).toBeInTheDocument();
    expect(screen.getByText("Partial answer")).toBeInTheDocument();
  });

  it("explains a refusal that happens before streaming starts (409) and stays usable", async () => {
    setup({ onSend: () => jsonResponse(409, errorBody("stream_in_progress", "A reply is already being generated for this conversation.")) });
    await userEvent.type(await box(), "too soon");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText(/already being generated/i)).toBeInTheDocument();
    await userEvent.type(await box(), "again");
    expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();
  });

  it("keeps the dismissible error out of the way once closed", async () => {
    setup({ onSend: () => jsonResponse(404, errorBody("conversation_not_found", "Conversation not found")) });
    await userEvent.type(await box(), "hi");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    const alert = await screen.findByText("Conversation not found");
    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    await waitFor(() => expect(alert).not.toBeInTheDocument());
  });
});
