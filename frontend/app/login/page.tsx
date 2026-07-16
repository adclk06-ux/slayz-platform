"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import {
  CheckCircle2,
  LineChart,
  Loader2,
  LockKeyhole,
  MessageSquare,
  Newspaper,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { fetchSetupStatus, login, setAuthSession } from "@/lib/api";

const platformFeatures = [
  {
    icon: Newspaper,
    title: "Kurumsal Haber Akışı",
    description: "Güncel gelişmeleri tek merkezden takip edin.",
  },
  {
    icon: LineChart,
    title: "Piyasa Terminali",
    description: "Hisseler, grafikler ve AI destekli analizler.",
  },
  {
    icon: MessageSquare,
    title: "Desk Chat",
    description: "Ekip arkadaşlarınızla güvenli kurum içi iletişim.",
  },
  {
    icon: Sparkles,
    title: "Slayz Intelligence",
    description: "Araştırma ve platform kullanımı için akıllı asistan.",
  },
];

const loadingSteps = [
  "Kimlik doğrulandı",
  "Güvenli oturum hazırlanıyor",
  "Piyasa terminali bağlanıyor",
  "Slayz Intelligence başlatılıyor",
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [displayName, setDisplayName] = useState("");

  useEffect(() => {
    fetchSetupStatus()
      .then((status) => {
        if (status.needs_setup) router.replace("/setup");
      })
      .catch(() => undefined);
  }, [router]);

  useEffect(() => {
    if (!launching) return;

    const timers = loadingSteps.map((_, index) =>
      window.setTimeout(() => setLoadingStep(index), index * 240),
    );
    const navigationTimer = window.setTimeout(() => {
      window.location.assign("/");
    }, loadingSteps.length * 240 + 260);

    return () => {
      timers.forEach(window.clearTimeout);
      window.clearTimeout(navigationTimer);
    };
  }, [launching]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const data = await login(email.trim().toLowerCase(), password);
      setAuthSession(data.access_token, data.full_name);
      setDisplayName(data.full_name);
      setLaunching(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Giriş başarısız.");
      setLoading(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#07101f] text-white">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-40 -top-32 h-[34rem] w-[34rem] rounded-full bg-indigo-500/20 blur-3xl" />
        <div className="absolute -bottom-48 right-[-8rem] h-[38rem] w-[38rem] rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.045)_1px,transparent_1px)] bg-[size:48px_48px]" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#07101f]/20 to-[#07101f]" />
      </div>

      <div className="relative mx-auto grid min-h-screen w-full max-w-7xl items-center gap-14 px-6 py-10 lg:grid-cols-[1.08fr_0.92fr] lg:px-10 xl:px-14">
        <section className="hidden lg:block">
          <div className="mb-10 flex items-center gap-4">
            <div className="relative h-16 w-16 overflow-hidden rounded-2xl border border-white/10 bg-white shadow-2xl shadow-indigo-950/50">
              <Image
                src="/images/slayz-logo.webp"
                alt="Slayz"
                fill
                sizes="64px"
                className="object-contain p-1"
                priority
              />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.28em] text-cyan-300">Slayz Enterprise</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight">Finansal Bilgi ve İletişim Platformu</h1>
            </div>
          </div>

          <div className="max-w-xl">
            <h2 className="text-4xl font-black leading-tight tracking-[-0.035em] xl:text-5xl">
              Kurumunuzun haber, piyasa ve iletişim merkezi.
            </h2>
            <p className="mt-5 max-w-lg text-base leading-7 text-slate-300">
              Slayz; araştırma ekiplerini güncel haberler, piyasa verileri, yapay zekâ destekli analiz ve gerçek zamanlı ekip iletişimiyle tek çalışma alanında buluşturur.
            </p>
          </div>

          <div className="mt-10 grid max-w-2xl grid-cols-2 gap-4">
            {platformFeatures.map(({ icon: Icon, title, description }) => (
              <div key={title} className="rounded-2xl border border-white/10 bg-white/[0.045] p-4 backdrop-blur-xl transition hover:border-cyan-300/25 hover:bg-white/[0.07]">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300/15 bg-cyan-300/10 text-cyan-200">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-sm font-bold text-white">{title}</h3>
                <p className="mt-1 text-xs leading-5 text-slate-400">{description}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-md">
          <div className="mb-7 flex items-center gap-3 lg:hidden">
            <div className="relative h-14 w-14 overflow-hidden rounded-2xl border border-white/10 bg-white shadow-xl">
              <Image src="/images/slayz-logo.webp" alt="Slayz" fill sizes="56px" className="object-contain p-1" priority />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">Slayz Enterprise</p>
              <h1 className="mt-0.5 text-lg font-bold">Kurumsal Çalışma Alanı</h1>
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-white/10 bg-white/[0.075] p-1 shadow-2xl shadow-black/30 backdrop-blur-2xl">
            <form onSubmit={handleSubmit} className="rounded-[1.5rem] border border-white/10 bg-[#0d1728]/95 p-6 sm:p-8">
              <div className="mb-7">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-300/15 bg-emerald-300/10 px-3 py-1.5 text-[11px] font-bold text-emerald-200">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Güvenli kurumsal erişim
                </div>
                <h2 className="text-2xl font-black tracking-tight text-white">Tekrar hoş geldiniz</h2>
                <p className="mt-2 text-sm leading-6 text-slate-400">Slayz çalışma alanınıza kurumsal hesabınızla giriş yapın.</p>
              </div>

              {error && (
                <div className="mb-5 rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">
                  {error}
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label className="mb-2 block text-xs font-bold text-slate-300">Kurumsal e-posta</label>
                  <input
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-white/[0.055] px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-cyan-300/45 focus:bg-white/[0.075] focus:ring-4 focus:ring-cyan-300/10"
                    placeholder="ad.soyad@slayz.com"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-xs font-bold text-slate-300">Şifre</label>
                  <input
                    type="password"
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-white/[0.055] px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-cyan-300/45 focus:bg-white/[0.075] focus:ring-4 focus:ring-cyan-300/10"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading || launching}
                className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-cyan-500 px-4 py-3 text-sm font-black text-white shadow-lg shadow-indigo-950/40 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-cyan-950/40 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <LockKeyhole className="h-4 w-4" />}
                {loading ? "Kimlik doğrulanıyor..." : "Güvenli Giriş"}
              </button>

              <div className="mt-6 grid gap-2 border-t border-white/10 pt-5 sm:grid-cols-2">
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-300" />
                  TLS ile şifrelenmiş bağlantı
                </div>
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-300" />
                  Kurumsal kimlik doğrulama
                </div>
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-300" />
                  Şifre tarayıcıda saklanmaz
                </div>
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-300" />
                  Yenilenebilir güvenli oturum
                </div>
              </div>
            </form>
          </div>

          <div className="mt-5 flex flex-col items-center justify-between gap-2 text-center text-[10px] uppercase tracking-[0.16em] text-slate-500 sm:flex-row sm:text-left">
            <span>© 2026 Slayz</span>
            <span>Enterprise Platform · v1.0</span>
          </div>
        </section>
      </div>

      {launching && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#07101f]/95 px-6 backdrop-blur-xl">
          <div className="w-full max-w-sm text-center">
            <div className="relative mx-auto mb-6 h-20 w-20 overflow-hidden rounded-2xl border border-white/10 bg-white shadow-2xl shadow-indigo-900/50">
              <Image src="/images/slayz-logo.webp" alt="Slayz" fill sizes="80px" className="object-contain p-1" priority />
            </div>
            <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Slayz Enterprise</p>
            <h2 className="mt-3 text-2xl font-black">Terminal hazırlanıyor</h2>
            <p className="mt-2 text-sm text-slate-400">Hoş geldiniz, {displayName}</p>

            <div className="mt-8 space-y-3 rounded-2xl border border-white/10 bg-white/[0.05] p-5 text-left">
              {loadingSteps.map((step, index) => {
                const complete = index < loadingStep;
                const active = index === loadingStep;
                return (
                  <div key={step} className={`flex items-center gap-3 text-sm transition ${index <= loadingStep ? "text-slate-100" : "text-slate-600"}`}>
                    {complete ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" />
                    ) : active ? (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-cyan-300" />
                    ) : (
                      <span className="h-4 w-4 shrink-0 rounded-full border border-slate-700" />
                    )}
                    <span>{step}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
