import { api } from "./client";

export interface ActionRecord {
  id: string;
  type: string;
  summary: string;
  payload: Record<string, unknown>;
  status: "proposed" | "approved" | "dismissed" | "expired";
  created_at: string;
  expires_at: string;
  decided_at: string | null;
  result: Record<string, unknown> | null;
  /** True only when the server would accept a decision from this user right now. */
  can_decide: boolean;
}

export interface AuditEvent {
  id: string;
  action: string;
  actor_name: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export const getAction = (id: string) => api<ActionRecord>(`/actions/${id}`);
export const executeAction = (id: string) => api<ActionRecord>(`/actions/${id}/execute`, { method: "POST" });
export const dismissAction = (id: string) => api<ActionRecord>(`/actions/${id}/dismiss`, { method: "POST" });
export const listAudit = () => api<{ items: AuditEvent[] }>("/audit");
