"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Search, Send, X } from "lucide-react";
import {
  AIPredictResponse,
  ChatUser,
  createRoom,
  fetchChatUsers,
  sendRoomMessage,
  Ticker,
} from "@/lib/api";

interface ShareTickerModalProps {
  ticker: Ticker | null;
  analysis: AIPredictResponse | null;
  onClose: () => void;
}

function formatPrice(value: string | null, currency: string | null) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "Fiyat alınamadı";
  return `${parsed.toLocaleString("tr-TR", { maximumFractionDigits: 4 })} ${currency || ""}`.trim();
}

export default function ShareTickerModal({ ticker, analysis, onClose }: ShareTickerModalProps) {
  const [users, setUsers] = useState<ChatUser[]>([]);
  const [query, setQuery] = useState("");
  const [sendingTo, setSendingTo] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includeAnalysis, setIncludeAnalysis] = useState(Boolean(analysis));

  useEffect(() => {
    if (!ticker) return;
    setQuery("");
    setSentTo(null);
    setError(null);
    setIncludeAnalysis(Boolean(analysis));
    fetchChatUsers()
      .then(setUsers)
      .catch((err) => setError(err instanceof Error ? err.message : "Ekip listesi yüklenemedi."));
  }, [ticker, analysis]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("tr-TR");
    return users.filter(
      (user) =>
        !needle ||
        user.full_name.toLocaleLowerCase("tr-TR").includes(needle) ||
        user.role.toLocaleLowerCase("tr-TR").includes(needle)
    );
  }, [query, users]);

  if (!ticker) return null;

  async function share(user: ChatUser) {
    setSendingTo(user.id);
    setError(null);
    try {
      const room = await createRoom({ type: "direct", member_ids: [user.id] });
      const change = Number(ticker?.change_percent || 0);
      const lines = [
        `📈 ${ticker?.symbol} · ${ticker?.name}`,
        `Fiyat: ${formatPrice(ticker?.price || null, ticker?.currency || null)}`,
        `Günlük değişim: ${change >= 0 ? "+" : ""}${change.toFixed(2)}%`,
        `Veri kaynağı: ${ticker?.source || "bilinmiyor"}`,
        `${window.location.origin}/terminal?ticker=${encodeURIComponent(ticker!.symbol)}`,
      ];
      if (includeAnalysis && analysis) {
        lines.push("", "🤖 Slayz AI özeti", analysis.summary, `Görünüm: ${analysis.stance} · Güven: ${analysis.confidence}`);
        if (analysis.risks.length) lines.push(`Riskler: ${analysis.risks.slice(0, 3).join("; ")}`);
      }
      lines.push("", "Bu içerik yatırım tavsiyesi değildir.");
      await sendRoomMessage(room.id, lines.join("\n"));
      setSentTo(user.full_name);
      setTimeout(onClose, 1100);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hisse paylaşılamadı.");
    } finally {
      setSendingTo(null);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="w-full max-w-md overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="font-bold text-slate-950">Hisseyi kiminle paylaşacaksın?</h2>
            <p className="mt-1 text-xs text-slate-500">{ticker.symbol} · {ticker.name}</p>
          </div>
          <button onClick={onClose} className="rounded-xl p-2 text-slate-500 hover:bg-slate-100" aria-label="Kapat">
            <X className="h-4 w-4" />
          </button>
        </div>

        {sentTo ? (
          <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
            <CheckCircle2 className="h-11 w-11 text-emerald-500" />
            <div className="font-semibold text-slate-900">{sentTo} kişisine gönderildi</div>
            <p className="text-xs text-slate-500">Hisse kartı direkt mesaj odasına kaydedildi.</p>
          </div>
        ) : (
          <>
            <div className="space-y-3 p-4">
              <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3">
                <Search className="h-4 w-4 text-slate-400" />
                <input
                  autoFocus
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Ekip arkadaşı ara..."
                  className="w-full py-2.5 text-sm outline-none"
                />
              </div>
              {analysis && (
                <label className="flex cursor-pointer items-center justify-between rounded-xl border border-indigo-100 bg-indigo-50/60 px-3 py-2.5 text-xs text-indigo-950">
                  <span>AI analiz özetini mesaja ekle</span>
                  <input
                    type="checkbox"
                    checked={includeAnalysis}
                    onChange={(event) => setIncludeAnalysis(event.target.checked)}
                    className="h-4 w-4 accent-indigo-600"
                  />
                </label>
              )}
              {error && <div className="rounded-xl bg-rose-50 p-3 text-xs text-rose-700">{error}</div>}
            </div>
            <div className="max-h-[390px] overflow-y-auto px-3 pb-4">
              {filtered.length === 0 ? (
                <div className="py-10 text-center text-sm text-slate-400">Aktif ekip arkadaşı bulunamadı.</div>
              ) : (
                filtered.map((user) => (
                  <button
                    key={user.id}
                    disabled={Boolean(sendingTo)}
                    onClick={() => share(user)}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-slate-50 disabled:opacity-50"
                  >
                    <div className="relative grid h-10 w-10 place-items-center rounded-full bg-indigo-100 font-bold text-indigo-700">
                      {user.full_name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}
                      <span className={`absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-white ${user.is_online ? "bg-emerald-500" : "bg-slate-300"}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-slate-900">{user.full_name}</div>
                      <div className="text-[11px] text-slate-400">{user.is_online ? "Çevrimiçi" : "Çevrimdışı"}</div>
                    </div>
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600">
                      <Send className="h-3.5 w-3.5" />
                      {sendingTo === user.id ? "Gönderiliyor" : "Gönder"}
                    </span>
                  </button>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
