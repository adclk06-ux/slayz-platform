"use client";

import { useState } from "react";
import { Mail, X } from "lucide-react";
import { shareArticle } from "@/lib/api";

interface ShareArticleModalProps {
  articleId: string;
  articleTitle: string;
  onClose: () => void;
}

export default function ShareArticleModal({ articleId, articleTitle, onClose }: ShareArticleModalProps) {
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSend() {
    if (!email.trim()) {
      setError("Lütfen bir e-posta adresi girin.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      await shareArticle(articleId, email.trim(), note.trim() || undefined);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Haber gönderilemedi.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/40 backdrop-blur-sm px-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-white border border-slate-100 shadow-2xl p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center">
              <Mail className="w-4 h-4 text-slate-600" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Ekip Arkadaşına Gönder</h3>
              <p className="text-xs text-slate-400 line-clamp-1 max-w-[220px]">{articleTitle}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-50 transition" aria-label="Kapat">
            <X className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        {success ? (
          <div className="py-6 text-center">
            <div className="w-12 h-12 mx-auto rounded-full bg-emerald-50 flex items-center justify-center mb-3">
              <Mail className="w-5 h-5 text-emerald-600" />
            </div>
            <p className="text-sm font-medium text-slate-900 mb-1">Haber gönderildi</p>
            <p className="text-xs text-slate-400">{email} adresine e-posta iletildi.</p>
            <button
              onClick={onClose}
              className="mt-5 w-full py-2.5 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition"
            >
              Kapat
            </button>
          </div>
        ) : (
          <div className="space-y-3.5">
            {error && (
              <div className="p-3 rounded-lg bg-rose-50 text-rose-600 text-xs border border-rose-100">{error}</div>
            )}
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5">Ekip Arkadaşının E-postası</label>
              <input
                type="email"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ornek@slayz.com"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-100 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5">Not (opsiyonel)</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                placeholder="Bu haberi neden paylaştığınızı ekleyin..."
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-100 text-sm text-slate-900 resize-none focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300"
              />
            </div>
            <button
              onClick={handleSend}
              disabled={sending}
              className="w-full py-2.5 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition disabled:opacity-60"
            >
              {sending ? "Gönderiliyor..." : "Gönder"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
