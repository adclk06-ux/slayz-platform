"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { bootstrapAdmin, fetchSetupStatus, login, setAuthSession } from "@/lib/api";
import { ShieldCheck } from "lucide-react";

export default function SetupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [domain, setDomain] = useState("slayz.com");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSetupStatus()
      .then((status) => {
        setDomain(status.allowed_email_domain);
        if (!status.needs_setup) router.replace("/login");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Kurulum durumu alınamadı."));
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Şifreler eşleşmiyor.");
      return;
    }
    setLoading(true);
    try {
      await bootstrapAdmin({ full_name: fullName, email, password });
      const session = await login(email.trim().toLowerCase(), password);
      setAuthSession(session.access_token, session.full_name);
      router.replace("/admin/users");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kurulum tamamlanamadı.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-6 py-10">
      <form onSubmit={submit} className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-7 shadow-sm space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="relative w-12 h-12 rounded-xl overflow-hidden border border-slate-100"><Image src="/images/slayz-logo.webp" alt="Slayz" fill className="object-contain" /></div>
          <div><h1 className="font-bold text-slate-900">İlk Yönetici Kurulumu</h1><p className="text-xs text-slate-500">Bu ekran yalnızca ilk kurulumda çalışır.</p></div>
        </div>
        {error && <div className="rounded-xl border border-rose-100 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
        <label className="block text-xs font-semibold text-slate-600">Ad soyad<input required minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20" /></label>
        <label className="block text-xs font-semibold text-slate-600">Yönetici e-postası<input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={`admin@${domain}`} className="mt-1.5 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20" /></label>
        <label className="block text-xs font-semibold text-slate-600">Şifre<input required minLength={8} type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20" /></label>
        <label className="block text-xs font-semibold text-slate-600">Şifre tekrar<input required minLength={8} type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20" /></label>
        <button disabled={loading} className="w-full rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60 flex items-center justify-center gap-2"><ShieldCheck className="w-4 h-4" />{loading ? "Kuruluyor..." : "Yönetici Hesabını Oluştur"}</button>
      </form>
    </div>
  );
}
