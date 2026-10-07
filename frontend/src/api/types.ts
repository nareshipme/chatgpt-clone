export interface Tenant {
  id: string;
  name: string;
  industry: string;
}

export interface Persona {
  id: string;
  name: string;
  description: string;
  starters: string[];
  selected: boolean;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  tenant_id: string;
  role: "planner" | "manager" | "viewer";
  persona?: string | null;
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
  data: Record<string, string | number | null>[];
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
/** A card to approve or dismiss something the assistant proposes. Only the id is stored here; status comes from the API. */
export interface ProposalPart {
  type: "proposal";
  action_id: string;
  action_type: string;
  summary: string;
}

export type MessagePart = TextPart | TablePart | ChartPart | ImagePart | ActionsPart | ProposalPart;

/** Progress of a tool the assistant is running (from the `tool` stream event). */
export interface ToolEvent {
  id: string;
  name: string;
  status: "running" | "done" | "error";
  message?: string | null;
}

export interface Provenance {
  tool: string;
  source: string;
  as_of: string;
  confidence: "high" | "medium" | "low";
  assumptions: string[];
  inputs: Record<string, unknown>;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  parts: MessagePart[];
  status: "streaming" | "complete" | "interrupted" | "error";
  /** Server-side facts about how the answer was made, e.g. which tools were used. */
  meta?: { provenance?: Provenance[] } | null;
  created_at: string;
}

export interface MessageList {
  items: Message[];
}
