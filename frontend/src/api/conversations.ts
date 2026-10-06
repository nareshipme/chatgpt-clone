import { api } from "./client";
import type { Conversation, ConversationPage } from "./types";

export interface ListParams {
  q?: string;
  cursor?: string | null;
  limit?: number;
}

export function listConversations({ q, cursor, limit = 20 }: ListParams = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (q) params.set("q", q);
  if (cursor) params.set("cursor", cursor);
  return api<ConversationPage>(`/conversations?${params}`);
}

export const getConversation = (id: string) => api<Conversation>(`/conversations/${id}`);

export const createConversation = (title?: string) =>
  api<Conversation>("/conversations", { method: "POST", body: title ? { title } : {} });

export const renameConversation = (id: string, title: string) =>
  api<Conversation>(`/conversations/${id}`, { method: "PATCH", body: { title } });

export const deleteConversation = (id: string) => api<void>(`/conversations/${id}`, { method: "DELETE" });
