"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AuthUser, clearAuthSession, getCurrentUser, logout, refreshSession, setAuthSession } from "@/lib/api";

interface AuthContextValue { user: AuthUser | null; loading: boolean; refresh: () => Promise<void>; signOut: () => Promise<void>; }
const AuthContext = createContext<AuthContextValue>({ user: null, loading: true, refresh: async () => {}, signOut: async () => {} });
export function useAuth() { return useContext(AuthContext); }
const PUBLIC_ROUTES = ["/login", "/setup", "/landing"];
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const running = useRef(false);

  const refresh = useCallback(async () => {
    if (typeof window === "undefined" || running.current) return;
    running.current = true;
    setLoading(true);
    let authenticated = false;
    let lastError: unknown = null;
    try {
      // Render free instances can need time to wake. Never destroy a valid
      // local session merely because the network is temporarily unavailable.
      for (let attempt = 0; attempt < 6; attempt += 1) {
        try {
          const token = window.localStorage.getItem("slayz_token");
          if (!token) {
            const session = await refreshSession();
            setAuthSession(session.access_token, session.full_name);
          }
          const me = await getCurrentUser();
          setUser(me);
          authenticated = true;
          break;
        } catch (err) {
          lastError = err;
          try {
            const session = await refreshSession();
            setAuthSession(session.access_token, session.full_name);
            const me = await getCurrentUser();
            setUser(me);
            authenticated = true;
            break;
          } catch (refreshErr) {
            lastError = refreshErr;
          }
          await wait(Math.min(1500 * (attempt + 1), 6000));
        }
      }
      if (!authenticated) {
        // Only clear credentials after repeated definitive auth failures.
        const message = String(lastError || "").toLowerCase();
        if (message.includes("401") || message.includes("oturum") || message.includes("kullanıcı bulunamadı")) {
          clearAuthSession();
          setUser(null);
        }
      }
    } finally {
      setLoading(false);
      running.current = false;
    }
  }, []);

  const signOut = async () => {
    try { await logout(); } catch {}
    clearAuthSession();
    setUser(null);
    window.location.assign("/login");
  };

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const resume = () => { if (document.visibilityState === "visible") void refresh(); };
    window.addEventListener("online", resume);
    document.addEventListener("visibilitychange", resume);
    const timer = window.setInterval(() => void refresh(), 6 * 60 * 1000);
    return () => { window.removeEventListener("online", resume); document.removeEventListener("visibilitychange", resume); window.clearInterval(timer); };
  }, [refresh]);

  useEffect(() => {
    if (loading) return;
    if (!user && !PUBLIC_ROUTES.includes(pathname)) router.replace("/login");
  }, [loading, pathname, router, user]);

  const isPublic = PUBLIC_ROUTES.includes(pathname);
  return <AuthContext.Provider value={{ user, loading, refresh, signOut }}>
    {loading && !isPublic ? (
      <div className="grid min-h-screen place-items-center bg-slate-50 px-6 text-center">
        <div><div className="mx-auto mb-4 h-9 w-9 animate-spin rounded-full border-4 border-indigo-100 border-t-indigo-600" />
        <div className="font-semibold text-slate-800">Slayz hazırlanıyor</div>
        <div className="mt-1 text-sm text-slate-500">Güvenli oturum ve canlı veriler bağlanıyor…</div></div>
      </div>
    ) : children}
  </AuthContext.Provider>;
}
