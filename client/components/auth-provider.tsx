"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiGet, apiSend } from "@/lib/client-api";
import type { Me } from "@/lib/types";

type AuthState = {
  me: Me | null; // null while loading
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const ANONYMOUS: Me = { authenticated: false, email: null, name: null };
const AuthContext = createContext<AuthState>({
  me: null,
  refresh: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMe(await apiGet<Me>("/api/me"));
    } catch {
      setMe(ANONYMOUS);
    }
  }, []);

  const logout = useCallback(async () => {
    await apiSend("POST", "/api/auth/logout");
    setMe(ANONYMOUS);
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<Me>("/api/me").then(
      (value) => !cancelled && setMe(value),
      () => !cancelled && setMe(ANONYMOUS),
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(() => ({ me, refresh, logout }), [me, refresh, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
