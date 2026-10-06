import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, refreshSession, setAccessToken, setSessionExpiredHandler } from "../api/client";
import type { AuthResponse, User } from "../api/types";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthValue {
  user: User | null;
  status: Status;
  /** True after the user chose to sign out (not after a session expiry). Used to forget the return-to page. */
  signedOut: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string, tenantId?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [signedOut, setSignedOut] = useState(false);
  const queryClient = useQueryClient();

  // Whenever the signed-in identity changes (sign out, expiry, sign in), drop every cached server response.
  // Otherwise the next user in the same tab would briefly see the previous user's data.
  const clear = useCallback(() => {
    void queryClient.cancelQueries();
    queryClient.clear();
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
  }, [queryClient]);

  // On page load, silently restore the session from the refresh cookie (the access token is memory-only).
  useEffect(() => {
    let active = true;
    refreshSession().then((data) => {
      if (!active) return;
      if (data) {
        setUser(data.user);
        setStatus("authenticated");
      } else {
        setStatus("anonymous");
      }
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setSessionExpiredHandler(clear);
    return () => setSessionExpiredHandler(null);
  }, [clear]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<AuthResponse>("/auth/login", { method: "POST", body: { email, password }, auth: false });
    queryClient.clear(); // a fresh session starts with an empty cache
    setSignedOut(false);
    setAccessToken(data.access_token);
    setUser(data.user);
    setStatus("authenticated");
  }, [queryClient]);

  const register = useCallback(
    async (email: string, password: string, displayName: string, tenantId?: string) => {
      await api("/auth/register", {
        method: "POST",
        body: { email, password, display_name: displayName, ...(tenantId ? { tenant_id: tenantId } : {}) },
        auth: false,
      });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST", auth: false });
    } finally {
      setSignedOut(true);
      clear();
    }
  }, [clear]);

  const value = useMemo(
    () => ({ user, status, signedOut, login, register, logout }),
    [user, status, signedOut, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
