import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, refreshSession, setAccessToken, setSessionExpiredHandler } from "../api/client";
import type { AuthResponse, User } from "../api/types";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthValue {
  user: User | null;
  status: Status;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  const clear = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

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
    setAccessToken(data.access_token);
    setUser(data.user);
    setStatus("authenticated");
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      await api("/auth/register", {
        method: "POST",
        body: { email, password, display_name: displayName },
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
      clear();
    }
  }, [clear]);

  const value = useMemo(() => ({ user, status, login, register, logout }), [user, status, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
