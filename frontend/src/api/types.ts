export interface User {
  id: string;
  email: string;
  display_name: string;
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

/** Parts are a tagged union: tables, charts, images and action buttons are added here later. */
export type MessagePart = TextPart;

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
