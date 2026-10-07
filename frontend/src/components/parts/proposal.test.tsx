import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { ActionRecord, AuditEvent } from "../../api/actions";
import type { Provenance } from "../../api/types";
import AuditPage from "../../pages/AuditPage";
import { MessageBubble } from "../MessageBubble";
import { ProposalView } from "./ProposalView";

vi.mock("../../auth/AuthContext", () => ({ useAuth: () => ({ user: { id: "u1" } }) }));
const api = vi.hoisted(() => ({ getAction: vi.fn(), executeAction: vi.fn(), dismissAction: vi.fn(), listAudit: vi.fn() }));
vi.mock("../../api/actions", () => api);

const part = { type: "proposal" as const, action_id: "a-1", action_type: "rebalance", summary: "Move 500 units of Pasta 500g from DC-2 to DC-5" };
const proposed: ActionRecord = {
  id: "a-1", type: "rebalance", summary: part.summary, payload: {}, status: "proposed", created_at: "", expires_at: "",
  decided_at: null, result: null, can_decide: true,
};
const approved: ActionRecord = {
  ...proposed, status: "approved", can_decide: false, decided_at: "2026-10-07T06:00:00Z",
  result: { estimated_cost_usd: 210, estimated_co2e_kg: 5, note: "Simulated: no real warehouse system was changed in this demo." },
};

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => vi.resetAllMocks());

describe("ProposalView", () => {
  it("shows the summary, the live status and the buttons only while a decision is possible", async () => {
    api.getAction.mockResolvedValue(proposed);
    wrap(<ProposalView part={part} />);
    expect(screen.getByText(part.summary)).toBeInTheDocument();
    expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Dismiss" })).toBeEnabled();
  });

  it("approving asks the server once, then shows the result and removes the buttons", async () => {
    api.getAction.mockResolvedValue(proposed);
    api.executeAction.mockResolvedValue(approved);
    wrap(<ProposalView part={part} />);
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByText("Approved")).toBeInTheDocument();
    expect(api.executeAction).toHaveBeenCalledTimes(1);
    expect(api.executeAction).toHaveBeenCalledWith("a-1");
    expect(screen.getByText(/Estimated cost: \$210/)).toBeInTheDocument();
    expect(screen.getByText(/Simulated: no real warehouse system/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument();
  });

  it("dismissing ends the proposal without approving anything", async () => {
    api.getAction.mockResolvedValue(proposed);
    api.dismissAction.mockResolvedValue({ ...proposed, status: "dismissed", can_decide: false });
    wrap(<ProposalView part={part} />);
    await userEvent.click(await screen.findByRole("button", { name: "Dismiss" }));
    expect(await screen.findByText("Dismissed")).toBeInTheDocument();
    expect(api.executeAction).not.toHaveBeenCalled();
  });

  it("does not offer buttons the server would refuse (a viewer), and says why", async () => {
    api.getAction.mockResolvedValue({ ...proposed, can_decide: false });
    wrap(<ProposalView part={part} />);
    expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByText(/can view this proposal but not approve it/i)).toBeInTheDocument();
  });

  it("when the server says it was already decided, shows that and the real status instead of the stale buttons", async () => {
    api.getAction.mockResolvedValueOnce(proposed).mockResolvedValue({ ...proposed, status: "dismissed", can_decide: false });
    api.executeAction.mockRejectedValue(new ApiError(409, "action_not_pending", "This action is already dismissed.", null));
    wrap(<ProposalView part={part} />);
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByText("This action is already dismissed.")).toBeInTheDocument();
    expect(await screen.findByText("Dismissed")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument());
  });

  it("an expired proposal shows as expired with no buttons", async () => {
    api.getAction.mockResolvedValue({ ...proposed, status: "expired", can_decide: false });
    wrap(<ProposalView part={part} />);
    expect(await screen.findByText("Expired")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("still shows what was proposed when the status cannot be loaded", async () => {
    api.getAction.mockRejectedValue(new ApiError(500, "internal_error", "boom", null));
    wrap(<ProposalView part={part} />);
    expect(await screen.findByText(/Could not load the current status/, {}, { timeout: 4000 })).toBeInTheDocument(); // after its one retry
    expect(screen.getByText(part.summary)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });
});

describe("Why this answer", () => {
  const prov: Provenance[] = [
    {
      tool: "list_at_risk_shipments", source: "Harbor transportation visibility feed (demo data)", as_of: "2026-10-07T06:00:00Z",
      confidence: "medium", assumptions: ["Current ETA is the carrier's latest estimate and can still change."], inputs: { window_days: 7 },
    },
  ];

  it("is offered only when the reply was made with tools, and opens the details", async () => {
    const { rerender } = render(<MessageBubble role="assistant" text="Plain answer" />);
    expect(screen.queryByRole("button", { name: /why this answer/i })).not.toBeInTheDocument();
    rerender(<MessageBubble role="assistant" text="Grounded answer" provenance={prov} />);
    await userEvent.click(screen.getByRole("button", { name: /why this answer/i }));
    const drawer = await screen.findByRole("presentation");
    expect(within(drawer).getByText("shipments at risk")).toBeInTheDocument();
    expect(within(drawer).getByText(/Source: Harbor transportation visibility feed/)).toBeInTheDocument();
    expect(within(drawer).getByText(/Inputs: window_days = 7/)).toBeInTheDocument();
    expect(within(drawer).getByText("medium confidence")).toBeInTheDocument();
    expect(within(drawer).getByText(/latest estimate and can still change/)).toBeInTheDocument();
  });

  it("is not offered while the reply is still being written", () => {
    render(<MessageBubble role="assistant" parts={[{ type: "text", text: "so far" }]} provenance={prov} live />);
    expect(screen.queryByRole("button", { name: /why this answer/i })).not.toBeInTheDocument();
  });
});

describe("AuditPage", () => {
  const events: AuditEvent[] = [
    { id: "e2", action: "action.approved", actor_name: "Ada", payload: { summary: "Move 500 units" }, created_at: "2026-10-07T06:05:00Z" },
    { id: "e1", action: "action.proposed", actor_name: "Ada", payload: { summary: "Move 500 units" }, created_at: "2026-10-07T06:00:00Z" },
  ];

  it("lists who did what, in the order the server sent", async () => {
    api.listAudit.mockResolvedValue({ items: events });
    wrap(<AuditPage />);
    const table = await screen.findByRole("table", { name: "Audit events" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getAllByRole("cell")[2].textContent)).toEqual(["Approved", "Proposed"]);
    expect(within(rows[0]).getByText("Ada")).toBeInTheDocument();
  });

  it("says plainly when there is nothing yet, and when the role may not read the log", async () => {
    api.listAudit.mockResolvedValueOnce({ items: [] });
    const first = wrap(<AuditPage />);
    expect(await screen.findByText("Nothing has been proposed yet.")).toBeInTheDocument();
    first.unmount();
    api.listAudit.mockRejectedValueOnce(new ApiError(403, "role_not_allowed", "Viewers cannot read the audit log.", null));
    wrap(<AuditPage />);
    expect(await screen.findByText("Viewers cannot read the audit log.")).toBeInTheDocument();
  });
});
