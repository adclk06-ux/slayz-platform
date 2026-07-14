"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AuthUser, clearAuthSession, getCurrentUser, logout, refreshSession, setAuthSession } from "@/lib/api";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  refresh: async () => {},
  signOut: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

const isDev = process.env.NODE_ENV === "development";

function authDebug(event: string, detail?: Record<string, unknown>) {
  if (!isDev) return;
  // eslint-disable-next-line no-console
  console.debug(`[auth] ${event}`, detail ?? "");
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = async () => {
    const me = await getCurrentUser();
    authDebug("me_ok", { userId: me.id });
    setUser(me);
  };

  const refresh = async () => {
    if (typeof window === "undefined") return;
    const token = window.localStorage.getItem("slayz_token");
    authDebug("refresh_start", {
      pathname,
      hasToken: Boolean(token),
      hasAuthCookie: document.cookie.includes("slayz_authenticated=1"),
    });
    setLoading(true);
    try {
      if (token) {
        await loadUser();
      } else {
        const session = await refreshSession();
        setAuthSession(session.access_token, session.full_name);
        await loadUser();
      }
    } catch (meErr) {
      authDebug("me_failed", { error: String(meErr) });
      // Access token may be expired; try silent refresh once.
      try {
        const session = await refreshSession();
        authDebug("refresh_ok");
        setAuthSession(session.access_token, session.full_name);
        await loadUser();
      } catch (refreshErr) {
        authDebug("auth_refresh_failed", { error: String(refreshErr) });
        clearAuthSession();
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  };

  const signOut = async () => {
    try {
      await logout();
    } catch {
      // ignore logout errors
    }
    clearAuthSession();
    setUser(null);
    router.push("/login");
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Redirect unauthenticated users away from protected routes.
  // The guard waits for the initial auth check to finish before redirecting,
  // which prevents the protected page from flickering while /api/auth/me is in flight.
  useEffect(() => {
    authDebug("route_change", { pathname, loading, authenticated: Boolean(user) });
    if (loading) return;
    const publicRoutes = ["/login", "/setup", "/landing"];
    if (!user && !publicRoutes.includes(pathname)) {
      authDebug("redirect_to_login", { reason: "auth_missing", from: pathname });
      router.push("/login");
    }
  }, [user, loading, pathname, router]);

  return (
    <AuthContext.Provider value={{ user, loading, refresh, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
