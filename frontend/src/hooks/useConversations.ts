import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
} from "../api/conversations";

// One key factory so every cache read, write and invalidation agrees on the names.
export const conversationKeys = {
  all: ["conversations"] as const,
  list: (q: string) => ["conversations", "list", q] as const,
  detail: (id: string) => ["conversations", "detail", id] as const,
};

/** Cursor-paginated list (server keyset pagination). `fetchNextPage` loads the next 20. */
export function useConversationList(q: string) {
  return useInfiniteQuery({
    queryKey: conversationKeys.list(q),
    queryFn: ({ pageParam }) => listConversations({ q, cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
}

export function useConversation(id: string | undefined) {
  return useQuery({
    queryKey: conversationKeys.detail(id ?? ""),
    queryFn: () => getConversation(id!),
    enabled: !!id,
  });
}

export function useCreateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (title?: string) => createConversation(title),
    onSuccess: () => qc.invalidateQueries({ queryKey: conversationKeys.all }),
  });
}

export function useRenameConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameConversation(id, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: conversationKeys.all }),
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: conversationKeys.detail(id) });
      return qc.invalidateQueries({ queryKey: conversationKeys.all });
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
