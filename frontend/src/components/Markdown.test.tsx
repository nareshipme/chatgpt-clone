import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Markdown } from "./Markdown";
import { MessageBubble } from "./MessageBubble";

const writeText = vi.fn().mockResolvedValue(undefined);

beforeEach(() => {
  writeText.mockClear();
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
});

describe("Markdown rendering", () => {
  it("renders emphasis, lists and headings", () => {
    render(<Markdown>{"# Title\n\nSome **bold** and *italic* text.\n\n- one\n- two\n\n1. first\n2. second"}</Markdown>);
    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getByText("bold").tagName).toBe("STRONG");
    expect(screen.getByText("italic").tagName).toBe("EM");
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });

  it("renders GitHub-style tables as real table elements", () => {
    render(<Markdown>{"| Name | Qty |\n| --- | --- |\n| Apples | 3 |\n| Pears | 5 |"}</Markdown>);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["Name", "Qty"]);
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByText("Pears")).toBeInTheDocument();
  });

  it("highlights code blocks, labels the language and copies the code", async () => {
    const { container } = render(<Markdown>{"```python\nprint('hi')\nx = 1\n```"}</Markdown>);
    expect(container.querySelector("code.hljs, code.language-python")).not.toBeNull();
    expect(container.querySelector(".hljs-built_in, .hljs-string")).not.toBeNull(); // tokens were highlighted
    expect(screen.getByText("python")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copy code" }));
    expect(writeText).toHaveBeenCalledWith("print('hi')\nx = 1");
  });

  it("falls back to a plain 'code' label and still renders when the language is unknown", () => {
    render(<Markdown>{"```nonsenselang\nsome text\n```"}</Markdown>);
    expect(screen.getByText("nonsenselang")).toBeInTheDocument();
    expect(screen.getByText(/some text/)).toBeInTheDocument();
  });

  it("copes with an unfinished code fence (a reply that is still streaming)", () => {
    let container!: HTMLElement;
    expect(() => ({ container } = render(<Markdown>{"Here is code:\n\n```js\nconst a = 1;\n"}</Markdown>))).not.toThrow();
    // highlighting splits the line across <span>s, so check the combined text
    expect(container.textContent).toContain("const a = 1;");
  });
});

describe("Markdown safety", () => {
  it("never renders raw HTML: scripts and event handlers do not become elements", () => {
    const { container } = render(
      <Markdown>{'Hi <script>window.__pwned = true</script> <img src="https://x.test/a.png" onerror="window.__pwned=true"> <b onclick="x()">bold?</b>'}</Markdown>,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("[onerror], [onclick]")).toBeNull();
    expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined();
  });

  it("opens links in a new tab with noopener noreferrer", () => {
    render(<Markdown>{"[docs](https://example.com/page)"}</Markdown>);
    const link = screen.getByRole("link", { name: "docs" });
    expect(link).toHaveAttribute("href", "https://example.com/page");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
    expect(link.getAttribute("rel")).toContain("noreferrer");
  });

  it.each(["javascript:alert(1)", "data:text/html;base64,PHNjcmlwdD4=", "vbscript:x", "file:///etc/passwd"])(
    "drops dangerous link scheme %s",
    (url) => {
      render(<Markdown>{`[click me](${url})`}</Markdown>);
      expect(screen.queryByRole("link")).toBeNull();
      expect(screen.getByText("click me")).toBeInTheDocument(); // the text survives, the link does not
    },
  );

  it("allows mailto links", () => {
    render(<Markdown>{"[write](mailto:someone@example.com)"}</Markdown>);
    expect(screen.getByRole("link", { name: "write" })).toHaveAttribute("href", "mailto:someone@example.com");
  });

  it("loads https images lazily and without a referrer", () => {
    const { container } = render(<Markdown>{"![a cat](https://example.com/cat.png)"}</Markdown>);
    const img = container.querySelector("img")!;
    expect(img).toHaveAttribute("src", "https://example.com/cat.png");
    expect(img).toHaveAttribute("loading", "lazy");
    expect(img).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(img).toHaveAttribute("alt", "a cat");
  });

  it.each(["http://example.com/cat.png", "data:image/svg+xml;base64,AAAA", "javascript:alert(1)", "//example.com/cat.png"])(
    "does not load the image for %s",
    (url) => {
      const { container } = render(<Markdown>{`![a cat](${url})`}</Markdown>);
      expect(container.querySelector("img")).toBeNull();
      expect(screen.getByText(/a cat/)).toBeInTheDocument();
    },
  );
});

describe("MessageBubble", () => {
  it("renders an assistant reply as Markdown but leaves the user's own text untouched", async () => {
    const { container } = render(
      <>
        <MessageBubble role="assistant" text={"Here is **bold**"} status="complete" />
        <MessageBubble role="user" text={"I typed **not bold**"} />
      </>,
    );
    // The Markdown renderer is loaded on demand, so wait for it to arrive.
    await waitFor(() => expect(container.querySelector('[data-role="assistant"] strong')?.textContent).toBe("bold"));
    expect(container.querySelector('[data-role="user"] strong')).toBeNull();
    expect(screen.getByText("I typed **not bold**")).toBeInTheDocument();
  });

  it("copies the message's original Markdown text", async () => {
    render(<MessageBubble role="assistant" text={"Some **text**\n\n- a\n- b"} status="complete" />);
    await userEvent.click(screen.getByRole("button", { name: "Copy message" }));
    expect(writeText).toHaveBeenCalledWith("Some **text**\n\n- a\n- b");
    await waitFor(() => expect(screen.getByRole("button", { name: "Copy message" })).toBeInTheDocument());
  });

  it("offers no copy button on the user's messages or while a reply is still streaming", () => {
    const { rerender } = render(<MessageBubble role="user" text="hello" />);
    expect(screen.queryByRole("button", { name: "Copy message" })).toBeNull();
    rerender(<MessageBubble role="assistant" text="partial" live />);
    expect(screen.queryByRole("button", { name: "Copy message" })).toBeNull();
  });

  it("falls back to a hidden textarea when the Clipboard API is unavailable", async () => {
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    const exec = vi.fn().mockReturnValue(true);
    (document as unknown as { execCommand: typeof exec }).execCommand = exec;
    render(<MessageBubble role="assistant" text="fallback text" status="complete" />);
    await userEvent.click(screen.getByRole("button", { name: "Copy message" }));
    expect(exec).toHaveBeenCalledWith("copy");
  });
});
