import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiStream } from "../api/client";
import type { MessagePart, ToolEvent } from "../api/types";
import { listMessages } from "../api/messages";
import { readSse } from "../api/sse";
import { conversationKeys, useUserId } from "./useConversations";

/** The turn currently in flight: what the user just sent and the reply as it arrives. */
export interface LiveTurn {
  userText: string;
  /** The reply so far, as typed parts (text before and after a table stays in order). */
  parts: MessagePart[];
  /** Tools the assistant has run (or is running) for this reply. */
  tools: ToolEvent[];
}

/** Append streamed text to the last text part, or start a new one after a structured part. */
function appendText(parts: MessagePart[], piece: string): MessagePart[] {
  const last = parts[parts.length - 1];
  if (last?.type === "text") return [...parts.slice(0, -1), { type: "text", text: last.text + piece }];
  return [...parts, { type: "text", text: piece }];
}

const REFETCH_AFTER_STOP_MS = 500; // the server notices the disconnect a moment after we abort

interface TokenData {
  text: string;
}
interface ErrorData {
  message: string;
}

/**
 * Chat state for one conversation.
 *  - Saved history comes from the server (TanStack Query).
 *  - The turn in flight lives in local state while it streams, then the server copy replaces it:
 *    the stored message is the source of truth, so what you saw streaming is what you see after a reload.
 */
export function useChat(conversationId: string) {
  const qc = useQueryClient();
  const userId = useUserId();
  const history = useQuery({
    queryKey: conversationKeys.messages(userId, conversationId),
    queryFn: () => listMessages(conversationId),
  });

  const [live, setLive] = useState<LiveTurn | null>(null);
  // How many saved messages existed when the live turn began. The final refetch lands a moment before the live turn
  // is cleared; hiding anything newer than this keeps the reply from showing twice during that moment.
  const [baseCount, setBaseCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const streaming = live !== null;

  // Switching conversations (or leaving the page) stops any reply in flight; the server saves it as 'interrupted'.
  useEffect(() => {
    setLive(null);
    setError(null);
    return () => abortRef.current?.abort();
  }, [conversationId]);

  const refresh = useCallback(async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: conversationKeys.messages(userId, conversationId) }),
      qc.invalidateQueries({ queryKey: conversationKeys.lists(userId) }), // new title, new position
      qc.invalidateQueries({ queryKey: conversationKeys.detail(userId, conversationId) }),
    ]);
  }, [qc, userId, conversationId]);

  const send = useCallback(
    async (text: string) => {
      if (abortRef.current && streaming) return; // one reply at a time
      const controller = new AbortController();
      abortRef.current = controller;
      setError(null);
      setBaseCount(qc.getQueryData<{ items: unknown[] }>(conversationKeys.messages(userId, conversationId))?.items.length ?? 0);
      setLive({ userText: text, parts: [], tools: [] });
      let stoppedByUser = false;
      try {
        const res = await apiStream(`/conversations/${conversationId}/messages`, { body: { content: text }, signal: controller.signal });
        for await (const frame of readSse(res.body!)) {
          if (frame.event === "start") {
            // The server has already saved the question and named the chat: show the new title right away.
            void qc.invalidateQueries({ queryKey: conversationKeys.lists(userId) });
            void qc.invalidateQueries({ queryKey: conversationKeys.detail(userId, conversationId) });
          } else if (frame.event === "token") {
            const { text: piece } = frame.data as TokenData;
            setLive((l) => (l ? { ...l, parts: appendText(l.parts, piece) } : l));
          } else if (frame.event === "part") {
            // A structured part (table, chart, image, actions). The server has already validated it.
            const part = frame.data as MessagePart;
            setLive((l) => (l ? { ...l, parts: [...l.parts, part] } : l));
          } else if (frame.event === "tool") {
            const t = frame.data as ToolEvent;
            setLive((l) => {
              if (!l) return l;
              const known = l.tools.some((x) => x.id === t.id);
              return { ...l, tools: known ? l.tools.map((x) => (x.id === t.id ? t : x)) : [...l.tools, t] };
            });
          } else if (frame.event === "error") {
            setError((frame.data as ErrorData).message);
            break;
          } else if (frame.event === "done") {
            break;
          }
        }
      } catch (e) {
        if (controller.signal.aborted) {
          stoppedByUser = true;
        } else if (e instanceof ApiError) {
          setError(e.message);
        } else {
          setError("The connection was lost. Please try again.");
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        if (stoppedByUser) await new Promise((r) => setTimeout(r, REFETCH_AFTER_STOP_MS));
        await refresh();
        setLive(null);
      }
    },
    [conversationId, refresh, streaming, qc, userId],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return {
    messages: live ? (history.data?.items ?? []).slice(0, baseCount) : (history.data?.items ?? []),
    isLoading: history.isPending,
    loadError: history.error,
    live,
    streaming,
    error,
    dismissError: () => setError(null),
    send,
    stop,
  };
}
