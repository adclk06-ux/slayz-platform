"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Image from "next/image";
import Link from "next/link";
import { Activity, ArrowRight, Bot, Sparkles, Zap } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

const ThreeBitcoin = dynamic(() => import("@/components/ThreeBitcoin"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center text-slate-400">
      <Sparkles className="w-6 h-6 animate-pulse" />
    </div>
  ),
});

function useLiveSimulation() {
  const [btc, setBtc] = useState(68542.12);
  const [eth, setEth] = useState(3521.45);
  const [gold, setGold] = useState(2356.8);
  const [bist, setBist] = useState(10432.5);
  const [aiInsight, setAiInsight] = useState(
    "Bitcoin shows resistance near $69k; AI sentiment is positive."
  );

  const insights = [
    "Bitcoin shows resistance near $69k; AI sentiment is positive.",
    "Altın ons fiyatlarında volatilite artıyor; risk iştahı düşük.",
    "BIST 100 teknik göstergeleri aşırı alım bölgesine yaklaşıyor.",
    "Ethereum ağında günlük işlem hacmi yükseliş trendinde.",
    "Risk-off modu etkili; yatırımcılar emtia ve tahvile yöneliyor.",
  ];

  async function fetchInsight() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/market/ai-insight`);
      if (res.ok) {
        const data = await res.json();
        if (data.insight) setAiInsight(data.insight);
      }
    } catch {
      // keep current insight on network failure
    }
  }

  useEffect(() => {
    fetchInsight();
    const interval = setInterval(() => {
      setBtc((p) => p * (1 + (Math.random() - 0.48) * 0.0015));
      setEth((p) => p * (1 + (Math.random() - 0.48) * 0.0018));
      setGold((p) => p * (1 + (Math.random() - 0.5) * 0.0008));
      setBist((p) => p * (1 + (Math.random() - 0.5) * 0.0006));
      if (Math.random() > 0.7) {
        fetchInsight();
      } else if (Math.random() > 0.5) {
        setAiInsight(insights[Math.floor(Math.random() * insights.length)]);
      }
    }, 1200);
    return () => clearInterval(interval);
  }, []);

  return { btc, eth, gold, bist, aiInsight };
}

export default function LandingPage() {
  const { btc, eth, gold, bist, aiInsight } = useLiveSimulation();

  return (
    <div className="relative min-h-screen overflow-hidden bg-white">
      {/* Subtle animated background gradient */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute -top-40 -right-40 w-[800px] h-[800px] rounded-full bg-indigo-50/60 blur-3xl" />
        <div className="absolute bottom-0 left-0 w-[600px] h-[600px] rounded-full bg-amber-50/50 blur-3xl" />
      </div>

      {/* Logo watermark */}
      <div className="absolute top-6 left-6 z-20 flex items-center gap-3">
        <div className="relative w-10 h-10 rounded-xl overflow-hidden shadow-sm border border-slate-100 bg-white">
          <Image
            src="/images/slayz-logo.webp"
            alt="Slayz"
            fill
            sizes="40px"
            className="object-contain p-0.5"
            priority
          />
        </div>
        <div>
          <div className="text-sm font-bold text-slate-900">SLAYZ</div>
          <div className="text-[10px] text-slate-400 tracking-wide">HABER & VERİ OTOMasyonu</div>
        </div>
      </div>

      {/* Top right CTA */}
      <div className="absolute top-6 right-6 z-20 flex items-center gap-3">
        <Link
          href="/terminal"
          className="hidden sm:flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-slate-200 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition"
        >
          <Activity className="w-4 h-4 text-indigo-600" /> Piyasalar
        </Link>
        <Link
          href="/login"
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 text-white text-sm font-medium shadow-md shadow-slate-900/20 hover:bg-slate-800 transition"
        >
          Panele Giriş Yap <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      <main className="relative z-10 flex flex-col lg:flex-row items-center justify-center min-h-screen px-6 lg:px-16 py-24 gap-12">
        {/* Left copy */}
        <div className="max-w-xl lg:w-1/2 space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 text-white text-xs font-bold uppercase tracking-wider shadow-md shadow-indigo-900/10">
            <Zap className="w-3.5 h-3.5" /> Slayz Automation
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 leading-[1.1] tracking-tight">
            Finansal veriyi <span className="text-indigo-600">gerçek zamanlı</span> okuyun.
          </h1>
          <p className="text-lg text-slate-500 leading-relaxed">
            Yapay zeka destekli küratörlük, canlı piyasa terminali ve otomatik haber akışı —
            tümü tek bir premium platformda.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link
              href="/terminal"
              className="px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold shadow-lg shadow-indigo-200/50 hover:bg-indigo-700 transition"
            >
              Terminali Keşfet
            </Link>
            <Link
              href="/login"
              className="px-5 py-2.5 rounded-xl border border-slate-200 bg-white text-slate-700 text-sm font-semibold hover:bg-slate-50 transition"
            >
              Demo Girişi
            </Link>
          </div>
        </div>

        {/* Right 3D scene */}
        <div className="relative w-full lg:w-1/2 h-[500px] lg:h-[650px]">
          <ThreeBitcoin className="w-full h-full" />

          {/* Floating glass cards */}
          <div className="absolute top-8 left-4 sm:left-10 max-w-[220px] rounded-2xl border border-white/60 bg-white/80 backdrop-blur-md p-4 shadow-xl shadow-slate-200/40">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Real-Time Data</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <span className="text-slate-500">BTC</span>
                <span className="font-semibold text-slate-900">${btc.toFixed(2)}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-slate-500">ETH</span>
                <span className="font-semibold text-slate-900">${eth.toFixed(2)}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-slate-500">XAU</span>
                <span className="font-semibold text-slate-900">${gold.toFixed(2)}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-slate-500">XU100</span>
                <span className="font-semibold text-slate-900">{bist.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div className="absolute bottom-10 right-4 sm:right-10 max-w-[260px] rounded-2xl border border-white/60 bg-white/80 backdrop-blur-md p-4 shadow-xl shadow-slate-200/40">
            <div className="flex items-center gap-2 mb-2">
              <Bot className="w-4 h-4 text-indigo-600" />
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">AI Insights</span>
            </div>
            <p className="text-sm text-slate-700 leading-relaxed min-h-[3.5rem]">
              {aiInsight}
            </p>
          </div>

          <div className="absolute top-1/2 right-4 sm:right-6 -translate-y-1/2 hidden sm:block">
            <div className="rounded-2xl border border-white/60 bg-white/80 backdrop-blur-md px-4 py-3 shadow-xl shadow-slate-200/40">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">SLAYZ CO-PILOT</div>
              <div className="text-sm font-semibold text-slate-900">AI entegre terminal</div>
            </div>
          </div>
        </div>
      </main>

      {/* Bottom ticker strip */}
      <div className="fixed bottom-0 left-0 right-0 border-t border-slate-100 bg-white/90 backdrop-blur-md z-20">
        <div className="max-w-7xl mx-auto px-6 py-2 flex items-center gap-6 text-xs overflow-x-auto">
          <span className="font-bold text-slate-400 uppercase tracking-wider shrink-0">Live Ticker</span>
          <span className="shrink-0">BTC <span className="font-semibold text-slate-900">${btc.toFixed(2)}</span></span>
          <span className="shrink-0">ETH <span className="font-semibold text-slate-900">${eth.toFixed(2)}</span></span>
          <span className="shrink-0">XAU/USD <span className="font-semibold text-slate-900">${gold.toFixed(2)}</span></span>
          <span className="shrink-0">BIST 100 <span className="font-semibold text-slate-900">{bist.toFixed(2)}</span></span>
        </div>
      </div>
    </div>
  );
}
