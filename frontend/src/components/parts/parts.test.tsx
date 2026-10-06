import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ChartPart, MessagePart, TablePart } from "../../api/types";
import { partsToPlainText } from "../../lib/parts";
import { PartsView } from "../PartsView";
import { ActionsView } from "./ActionsView";
import { ImageView } from "./ImageView";
import { TableView } from "./TableView";

const table: TablePart = {
  type: "table",
  title: "Quarterly sales",
  columns: ["Region", "Q1"],
  rows: [["North", 120], ["South", null]],
};
const chart: ChartPart = {
  type: "chart", kind: "bar", title: "Revenue", x: "month",
  series: [{ key: "revenue", label: "Revenue" }],
  data: [{ month: "Jan", revenue: 120 }, { month: "Feb", revenue: 150 }],
};
const options = [
  { id: "a", label: "Bullets", value: "Answer in bullets." },
  { id: "b", label: "Short", value: "Answer shortly." },
];

describe("TableView", () => {
  it("renders the title, headers and cells (null becomes an empty cell)", () => {
    render(<TableView part={table} />);
    expect(screen.getByText("Quarterly sales")).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Region", "Q1"]);
    expect(screen.getAllByRole("row")).toHaveLength(3);
    expect(screen.getByText("North")).toBeInTheDocument();
  });

  it("shows markup inside a cell as plain text, never as elements", () => {
    const { container } = render(<TableView part={{ ...table, rows: [["<b>bold</b><img src=x onerror=alert(1)>", 1]] }} />);
    expect(container.querySelector("b, img")).toBeNull();
    expect(screen.getByText(/<b>bold<\/b>/)).toBeInTheDocument();
  });
});

describe("ImageView", () => {
  it("loads https images lazily and without a referrer", () => {
    const { container } = render(<ImageView part={{ type: "image", url: "https://example.com/a.png", alt: "A chart" }} />);
    const img = container.querySelector("img")!;
    expect(img).toHaveAttribute("loading", "lazy");
    expect(img).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(img).toHaveAttribute("alt", "A chart");
  });

  it.each(["http://example.com/a.png", "javascript:alert(1)", "data:image/png;base64,AAAA"])("refuses %s even if the server let it through", (url) => {
    const { container } = render(<ImageView part={{ type: "image", url, alt: "x" }} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/\[image: x\]/)).toBeInTheDocument();
  });

  it("falls back to text when the image fails to load", async () => {
    const { container } = render(<ImageView part={{ type: "image", url: "https://example.com/missing.png", alt: "Gone" }} />);
    container.querySelector("img")!.dispatchEvent(new Event("error"));
    expect(await screen.findByText(/\[image: Gone\]/)).toBeInTheDocument();
  });
});

describe("ActionsView", () => {
  it("sends the chosen option's value", async () => {
    const onChoose = vi.fn();
    render(<ActionsView part={{ type: "actions", prompt: "Pick a style", options }} active onChoose={onChoose} />);
    expect(screen.getByText("Pick a style")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Short" }));
    expect(onChoose).toHaveBeenCalledTimes(1);
    expect(onChoose).toHaveBeenCalledWith("Answer shortly.");
  });

  it("is not clickable when inactive (an old menu is history)", () => {
    const onChoose = vi.fn();
    render(<ActionsView part={{ type: "actions", options }} active={false} onChoose={onChoose} />);
    for (const b of screen.getAllByRole("button")) expect(b).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Bullets" })); // even a forced click must do nothing
    expect(onChoose).not.toHaveBeenCalled();
  });

  it("shows which option was chosen and keeps only that one readable", () => {
    render(<ActionsView part={{ type: "actions", options }} active={false} answeredWith="Answer in bullets." onChoose={() => {}} />);
    expect(screen.getByRole("button", { name: "Bullets" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Short" })).toBeDisabled();
  });
});

describe("PartsView", () => {
  it("renders every part type in order", async () => {
    const parts: MessagePart[] = [
      { type: "text", text: "Intro text" },
      table,
      chart,
      { type: "image", url: "https://example.com/p.png", alt: "Pic" },
      { type: "actions", prompt: "Next?", options },
    ];
    const { container } = render(<PartsView parts={parts} actionsActive onChoose={() => {}} />);
    expect(await screen.findByText("Intro text", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Quarterly sales" })).toBeInTheDocument();
    // the chart is lazy-loaded; its accessible description and data table appear once it arrives
    expect(await screen.findByRole("img", { name: /bar chart: Revenue/i }, { timeout: 5000 })).toBeInTheDocument();
    expect(container.querySelector("img[alt='Pic']")).not.toBeNull();
    expect(screen.getByRole("group", { name: "Next?" })).toBeInTheDocument();
  });

  it("gives charts a readable data table behind 'View data'", async () => {
    render(<PartsView parts={[chart]} />);
    const data = await screen.findByRole("table", { name: "Revenue data" }, { timeout: 3000 });
    expect(within(data).getByText("Jan")).toBeInTheDocument();
    expect(within(data).getByText("150")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("View data")).toBeInTheDocument());
  });

  it("leaves a blank cell for a gap in a series instead of printing 'null'", async () => {
    const gap: ChartPart = { ...chart, series: [{ key: "revenue", label: "Revenue" }, { key: "actual", label: "Actual" }], data: [{ month: "Jan", revenue: 120, actual: 118 }, { month: "Feb", revenue: 150, actual: null }] };
    render(<PartsView parts={[gap]} />);
    const data = await screen.findByRole("table", { name: "Revenue data" }, { timeout: 5000 });
    expect(within(data).queryByText("null")).toBeNull();
    expect(within(data).getByText("118")).toBeInTheDocument();
  });

  it("puts a cursor on the last text part while the reply is still arriving", async () => {
    render(<PartsView parts={[{ type: "text", text: "typing" }]} live />);
    expect(await screen.findByText(/typing ▍/)).toBeInTheDocument();
  });
});

describe("partsToPlainText (Copy message)", () => {
  it("makes tables paste-able into a spreadsheet and describes other parts briefly", () => {
    const text = partsToPlainText([
      { type: "text", text: "Here you go" },
      table,
      chart,
      { type: "image", url: "https://example.com/p.png", alt: "Pic" },
      { type: "actions", prompt: "Next?", options },
    ]);
    expect(text).toContain("Here you go");
    expect(text).toContain("Region\tQ1\nNorth\t120\nSouth\t");
    expect(text).toContain("[chart: Revenue]");
    expect(text).toContain("[image: Pic]");
    expect(text).toContain("Next?\nBullets | Short");
  });

  it("skips empty parts", () => {
    expect(partsToPlainText([{ type: "text", text: "" }, { type: "text", text: "hello" }])).toBe("hello");
  });
});
