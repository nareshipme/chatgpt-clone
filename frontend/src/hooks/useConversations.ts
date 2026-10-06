import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
} from "../api/conversations";

// One key factory so every cache read, write and invalidation agrees on the names.
// Every key starts with the user id: even if a cache clear were ever missed, one user's cached data
// could not be served to another user.
export const conversationKeys = {
  all: (userId: string) => ["conversations", userId] as const,
  list: (userId: string, q: string) => ["conversations", userId, "list", q] as const,
  detail: (userId: string, id: string) => ["conversations", userId, "detail", id] as const,
  messages: (userId: string, id: string) => ["conversations", userId, "messages", id] as const,
  lists: (userId: string) => ["conversations", userId, "list"] as const,
};

export function useUserId(): string {
  return useAuth().user?.id ?? "anonymous";
}

/** Cursor-paginated list (server keyset pagination). `fetchNextPage` loads the next 20. */
export function useConversationList(q: string) {
  const userId = useUserId();
  return useInfiniteQuery({
    queryKey: conversationKeys.list(userId, q),
    queryFn: ({ pageParam }) => listConversations({ q, cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    // While a new search is loading keep showing the previous results instead of flashing skeletons.
    placeholderData: keepPreviousData,
  });
}

export function useConversation(id: string | undefined) {
  const userId = useUserId();
  return useQuery({
    queryKey: conversationKeys.detail(userId, id ?? ""),
    queryFn: () => getConversation(id!),
    enabled: !!id,
  });
}

export function useCreateConversation() {
  const qc = useQueryClient();
  const userId = useUserId();
  return useMutation({
    mutationFn: (title?: string) => createConversation(title),
    onSuccess: () => qc.invalidateQueries({ queryKey: conversationKeys.all(userId) }),
  });
}

export function useRenameConversation() {
  const qc = useQueryClient();
  const userId = useUserId();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameConversation(id, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: conversationKeys.all(userId) }),
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  const userId = useUserId();
  return useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: conversationKeys.detail(userId, id) });
      return qc.invalidateQueries({ queryKey: conversationKeys.all(userId) });
    },
  });
}

/** Delay a fast-changing value (the search box) so we do not hit the API on every keystroke. */
export function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
