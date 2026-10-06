import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Tenant } from "../api/types";

/** The fictional demo companies. Public (no sign-in needed) and rarely changes. */
export function useTenants() {
  return useQuery({
    queryKey: ["tenants"],
    queryFn: () => api<Tenant[]>("/tenants", { auth: false }),
    staleTime: 60 * 60 * 1000,
    retry: 1,
  });
}
