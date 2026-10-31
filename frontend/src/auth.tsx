import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, tokenStore } from "./api";
import type { Me } from "./types";

interface AuthState {
  me: Me | null;
  signedIn: boolean;
  loading: boolean;
  submit: (mode: "login" | "register", fields: { email: string; password: string; name?: string }) => Promise<void>;
  logout: () => void;
  refresh: () => void;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(tokenStore.get());

  const meQuery = useQuery({ queryKey: ["me", token], queryFn: () => api<Me>("/auth/me"), enabled: !!token });

  const logout = useCallback(() => {
    tokenStore.clear();
    setToken(null);
    queryClient.clear(); // never show the next person the previous person's data
  }, [queryClient]);

  useEffect(() => {
    window.addEventListener("sessio:logout", logout);
    return () => window.removeEventListener("sessio:logout", logout);
  }, [logout]);

  const submit = useCallback(async (mode: "login" | "register", fields: { email: string; password: string; name?: string }) => {
    const res = await api<{ token: string }>(`/auth/${mode}`, { method: "POST", body: fields });
    tokenStore.set(res.token);
    setToken(res.token);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      me: token ? (meQuery.data ?? null) : null,
      signedIn: !!token,
      loading: !!token && meQuery.isLoading,
      submit,
      logout,
      refresh: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
    }),
    [token, meQuery.data, meQuery.isLoading, submit, logout, queryClient],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(Ctx);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
