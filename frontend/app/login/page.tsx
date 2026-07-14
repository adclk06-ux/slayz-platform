"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { fetchSetupStatus, login, setAuthSession } from "@/lib/api";
import { LockKeyhole } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSetupStatus()
      .then((status) => {
        if (status.needs_setup) router.replace("/setup");
      })
      .catch(() => undefined);
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await login(email.trim().toLowerCase(), password);
      setAuthSession(data.access_token, data.full_name);
      window.location.assign("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Giriş başarısız.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="relative w-20 h-20 rounded-2xl overflow-hidden shadow-md border border-slate-100 bg-white mb-4">
            <Image src="/images/slayz-logo.webp" alt="Slayz" fill sizes="80px" className="object-contain p-1" priority />
          </div>
          <h1 className="text-xl font-bold text-slate-900">Slayz Haber Otomasyonu</h1>
          <p className="text-sm text-slate-500 mt-1">Kurumsal çalışma alanı</p>
        </div>

        <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4 shadow-sm">
          {error && <div className="p-3 rounded-lg bg-rose-50 text-rose-700 text-sm border border-rose-100">{error}</div>}
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Kurumsal e-posta</label>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              placeholder="ad.soyad@slayz.com"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Şifre</label>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              placeholder="••••••••"
            />
          </div>
          <button type="submit" disabled={loading} className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition disabled:opacity-60">
            <LockKeyhole className="w-4 h-4" />
            {loading ? "Giriş yapılıyor..." : "Giriş Yap"}
          </button>
          <p className="text-[11px] leading-relaxed text-slate-400 text-center">
            Oturumunuz güvenli yenileme anahtarıyla 30 gün boyunca korunur. Şifreniz tarayıcıda saklanmaz.
          </p>
        </form>
      </div>
    </div>
  );
}
