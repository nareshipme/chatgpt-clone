import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiStream } from "../api/client";
import { listMessages } from "../api/messages";
import { readSse } from "../api/sse";
import { conversationKeys, useUserId } from "./useConversations";

/** The turn currently in flight: what the user just sent and the reply as it arrives. */
export interface LiveTurn {
  userText: string;
  assistantText: string;
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
      setLive({ userText: text, assistantText: "" });
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
            setLive((l) => (l ? { ...l, assistantText: l.assistantText + piece } : l));
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
    [conversationId, refresh, streaming],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return {
    messages: history.data?.items ?? [],
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
