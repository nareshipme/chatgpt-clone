import { api } from "./client";
import type { MessageList } from "./types";

export const listMessages = (conversationId: string) => api<MessageList>(`/conversations/${conversationId}/messages`);
