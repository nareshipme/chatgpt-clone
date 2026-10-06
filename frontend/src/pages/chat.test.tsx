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
  return { mock, setThread: (m: Message[]) => (thread = m), refetchAll: () => client.invalidateQueries() };
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

  it("refreshes the sidebar as soon as the reply starts, not only when it ends", async () => {
    let sse!: ReturnType<typeof sseResponse>;
    const { mock } = setup({ onSend: (init) => (sse = sseResponse(init)).response });
    await screen.findByLabelText("Message");
    const before = calls(mock, "GET /conversations?limit=20").length;
    await userEvent.type(screen.getByLabelText("Message"), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    await screen.findByRole("button", { name: "Stop generating" });
    sse.push("start", { assistant_message_id: "m2" });
    await waitFor(() => expect(calls(mock, "GET /conversations?limit=20").length).toBeGreaterThan(before));
    sse.close();
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

// ------------------------------------------------------------------ rich content in the chat
const rich = (id: string, role: Message["role"], parts: Message["parts"], status: Message["status"] = "complete"): Message => ({
  id, conversation_id: "c1", role, status, created_at: "", parts,
});
const menu = {
  type: "actions" as const,
  prompt: "How should I answer?",
  options: [
    { id: "bullets", label: "Bullet points", value: "Please answer in bullet points." },
    { id: "short", label: "One paragraph", value: "Please answer in one paragraph." },
  ],
};

describe("rich chat", () => {
  it("shows tables and images from saved history", async () => {
    setup({
      history: [
        rich("m1", "user", [{ type: "text", text: "show data" }]),
        rich("m2", "assistant", [
          { type: "text", text: "Here it is" },
          { type: "table", title: "Sales", columns: ["Region", "Q1"], rows: [["North", 120]] },
          { type: "image", url: "https://example.com/p.png", alt: "Chart picture" },
        ]),
      ],
    });
    expect(await screen.findByRole("table", { name: "Sales" })).toBeInTheDocument();
    expect(screen.getByText("North")).toBeInTheDocument();
    expect(document.querySelector("img[alt='Chart picture']")).not.toBeNull();
  });

  it("clicking a choice sends that option's text as the next message", async () => {
    let sse!: ReturnType<typeof sseResponse>;
    const { mock } = setup({
      history: [rich("m1", "user", [{ type: "text", text: "explain" }]), rich("m2", "assistant", [{ type: "text", text: "Sure." }, menu])],
      onSend: (init) => (sse = sseResponse(init)).response,
    });
    await userEvent.click(await screen.findByRole("button", { name: "Bullet points" }));
    await waitFor(() => expect(calls(mock, "POST /conversations/c1/messages")).toHaveLength(1));
    expect(JSON.parse(calls(mock, "POST /conversations/c1/messages")[0][1]!.body as string)).toEqual({ content: "Please answer in bullet points." });
    // while that reply streams, the menu cannot be used again and the chosen option is marked
    expect(await screen.findByRole("button", { name: "Bullet points" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "One paragraph" })).toBeDisabled();
    sse.close();
  });

  it("menus on older replies are history: disabled, with the user's earlier choice shown", async () => {
    setup({
      history: [
        rich("m1", "user", [{ type: "text", text: "explain" }]),
        rich("m2", "assistant", [{ type: "text", text: "Sure." }, menu]),
        rich("m3", "user", [{ type: "text", text: "Please answer in one paragraph." }]),
        rich("m4", "assistant", [{ type: "text", text: "Here is a paragraph." }]),
      ],
    });
    const chosen = await screen.findByRole("button", { name: "One paragraph" });
    expect(chosen).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Bullet points" })).toBeDisabled();
  });

  it("a menu on the newest finished reply is clickable, one on an unfinished reply is not", async () => {
    setup({
      history: [rich("m1", "user", [{ type: "text", text: "go" }]), rich("m2", "assistant", [{ type: "text", text: "Partial" }, menu], "interrupted")],
    });
    expect(await screen.findByRole("button", { name: "Bullet points" })).toBeDisabled(); // interrupted: do not offer choices
  });

  it("shows a table the moment it arrives mid-stream, between the surrounding text", async () => {
    let sse!: ReturnType<typeof sseResponse>;
    const { setThread } = setup({ onSend: (init) => (sse = sseResponse(init)).response });
    await userEvent.type(await box(), "table please");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));

    sse.push("token", { text: "Here is the table: " });
    await screen.findByText(/Here is the table/);
    sse.push("part", { type: "table", title: "Demo", columns: ["A"], rows: [["cell-1"]] });
    expect(await screen.findByRole("table", { name: "Demo" })).toBeInTheDocument();
    sse.push("token", { text: "That is all." });
    expect(await screen.findByText(/That is all\./)).toBeInTheDocument();

    const bubble = document.querySelector('[data-role="assistant"]')!;
    const order = Array.from(bubble.querySelectorAll("p, table")).map((el) => el.tagName + ":" + (el.textContent ?? "").slice(0, 12));
    expect(order[0]).toMatch(/^P:Here is the/);
    expect(order[1]).toMatch(/^TABLE:/);
    expect(order[2]).toMatch(/^P:That is all/);

    setThread([rich("m1", "user", [{ type: "text", text: "table please" }]), rich("m2", "assistant", [
      { type: "text", text: "Here is the table: " },
      { type: "table", title: "Demo", columns: ["A"], rows: [["cell-1"]] },
      { type: "text", text: "That is all." },
    ])]);
    sse.push("done", {});
    sse.close();
    await waitFor(() => expect(screen.getByRole("button", { name: "Send message" })).toBeInTheDocument());
    expect(screen.getAllByRole("table", { name: "Demo" })).toHaveLength(1); // no duplicate after the saved copy replaces the live one
  });
});

describe("hand-over from live reply to saved reply", () => {
  it("never shows the reply twice while the saved copy arrives", async () => {
    let sse!: ReturnType<typeof sseResponse>;
    const { mock, setThread, refetchAll } = setup({ onSend: (init) => (sse = sseResponse(init)).response });
    await userEvent.type(await box(), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    sse.push("token", { text: "Reply text" });
    await screen.findByText(/Reply text/);
    // the server copy exists (a refetch could land now) but the stream has not finished
    setThread([rich("m1", "user", [{ type: "text", text: "hello" }]), rich("m2", "assistant", [{ type: "text", text: "Reply text" }])]);
    const before = calls(mock, "GET /conversations/c1/messages").length;
    await refetchAll();
    await waitFor(() => expect(calls(mock, "GET /conversations/c1/messages").length).toBeGreaterThan(before));
    await new Promise((r) => setTimeout(r, 100)); // let React render the refetched list
    expect(document.querySelectorAll('[data-role="assistant"]')).toHaveLength(1);
    sse.push("done", {});
    sse.close();
    await waitFor(() => expect(screen.getByRole("button", { name: "Send message" })).toBeInTheDocument());
    expect(document.querySelectorAll('[data-role="assistant"]')).toHaveLength(1);
  });
});
