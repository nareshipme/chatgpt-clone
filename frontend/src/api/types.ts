export interface Tenant {
  id: string;
  name: string;
  industry: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  tenant_id: string;
  role: "planner" | "manager" | "viewer";
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface FieldError {
  field: string;
  message: string;
}

export interface Conversation {
  id: string;
  title: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConversationPage {
  items: Conversation[];
  next_cursor: string | null;
}

export interface TextPart {
  type: "text";
  text: string;
}

export interface TablePart {
  type: "table";
  title?: string | null;
  columns: string[];
  rows: (string | number | boolean | null)[][];
}

export interface ChartSeries {
  key: string;
  label: string;
}

export interface ChartPart {
  type: "chart";
  kind: "bar" | "line";
  title?: string | null;
  x: string;
  series: ChartSeries[];
  data: Record<string, string | number>[];
}

export interface ImagePart {
  type: "image";
  url: string;
  alt: string;
}

export interface ActionOption {
  id: string;
  label: string;
  /** Sent as the user's next message when this option is chosen. */
  value: string;
}

export interface ActionsPart {
  type: "actions";
  prompt?: string | null;
  options: ActionOption[];
}

/** A message is a list of typed parts. Mirrors the server's validated schema. */
export type MessagePart = TextPart | TablePart | ChartPart | ImagePart | ActionsPart;

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  parts: MessagePart[];
  status: "streaming" | "complete" | "interrupted" | "error";
  created_at: string;
}

export interface MessageList {
  items: Message[];
}
