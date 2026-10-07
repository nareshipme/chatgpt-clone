import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Persona, User } from "../api/types";
import { useUserId } from "./useConversations";

// Keyed by user id like every other per-user cache entry (see conversationKeys).
const personaKey = (userId: string) => ["personas", userId] as const;

/** The personas for the signed-in user's company, with the active one marked `selected`. */
export function usePersonas() {
  const userId = useUserId();
  return useQuery({ queryKey: personaKey(userId), queryFn: () => api<Persona[]>("/personas"), staleTime: 5 * 60 * 1000, retry: 1 });
}

export function useChoosePersona() {
  const qc = useQueryClient();
  const userId = useUserId();
  return useMutation({
    mutationFn: (persona: string) => api<User>("/me/settings", { method: "PATCH", body: { persona } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: personaKey(userId) }),
  });
}
