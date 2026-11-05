import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { authApi } from "../api/auth";
import { tokenStore } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState(tokenStore.get() ? "loading" : "anonymous");

  const loadUser = useCallback(async () => {
    if (!tokenStore.get()) {
      setUser(null);
      setStatus("anonymous");
      return null;
    }
    try {
      const me = await authApi.me();
      setUser(me);
      setStatus("authenticated");
      return me;
    } catch {
      tokenStore.clear();
      setUser(null);
      setStatus("anonymous");
      return null;
    }
  }, []);

  useEffect(() => {
    loadUser();
    const onExpired = () => {
      setUser(null);
      setStatus("anonymous");
    };
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, [loadUser]);

  const acceptToken = useCallback((response) => {
    tokenStore.set(response.access_token);
    setUser(response.user);
    setStatus("authenticated");
    return response.user;
  }, []);

  const value = useMemo(
    () => ({
      user,
      status,
      isAuthenticated: status === "authenticated",
      login: async (email, password) => acceptToken(await authApi.login({ email, password })),
      register: async (body) => acceptToken(await authApi.register(body)),
      acceptToken,
      refreshUser: loadUser,
      setUser,
      logout: async () => {
        try { await authApi.logout(); } catch { /* token may already be invalid */ }
        tokenStore.clear();
        setUser(null);
        setStatus("anonymous");
      },
    }),
    [user, status, acceptToken, loadUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
