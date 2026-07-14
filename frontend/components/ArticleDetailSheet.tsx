"use client";

import { useEffect, useState } from "react";
import { Article, analyzeArticle, fetchArticle, reviewArticle } from "@/lib/api";
import { X, ExternalLink, Sparkles, CheckCircle2, XCircle, ThumbsUp, ThumbsDown } from "lucide-react";
import Link from "next/link";

interface ArticleDetailSheetProps {
  article: Article;
  onClose: () => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  crypto: "Kripto Para",
  stocks: "Borsa",
  commodities: "Emtia / Altın",
  general: "Genel",
};

export default function ArticleDetailSheet({ article: initial, onClose }: ArticleDetailSheetProps) {
  const [article, setArticle] = useState<Article>(initial);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setArticle(initial);
  }, [initial.id]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      try {
        const data = await fetchArticle(initial.id);
        if (mounted) setArticle(data);
      } catch (err) {
        // keep initial article if detail fetch fails
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, [initial.id]);

  async function handleReview(approve: boolean) {
    setBusy(true);
    try {
      const updated = await reviewArticle(article.id, approve);
      setArticle(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setBusy(false);
    }
  }

  async function handleAnalyze() {
    setBusy(true);
    try {
      const updated = await analyzeArticle(article.id);
      setArticle(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setBusy(false);
    }
  }

  const paragraphs = (article.raw_content || "")
    .split(/\n+/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl h-full bg-white shadow-2xl overflow-y-auto animate-slide-in-right">
        <div className="sticky top-0 bg-white/90 backdrop-blur-md border-b border-slate-100 px-6 py-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full">
              {CATEGORY_LABELS[article.category] || "Genel"}
            </span>
            {article.is_mega_cap && (
              <span className="text-[11px] font-semibold uppercase tracking-wide bg-amber-50 text-amber-700 px-2.5 py-1 rounded-full border border-amber-100">
                Mega-Cap
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Link
              href={`/article/${article.id}`}
              className="p-2 rounded-lg hover:bg-slate-100 text-slate-500 transition"
              title="Tam detay sayfası"
            >
              <ExternalLink className="w-4 h-4" />
            </Link>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-slate-100 text-slate-500 transition"
              title="Kapat"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="px-6 py-6 space-y-6">
          {loading && (
            <div className="text-xs text-slate-400 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 animate-pulse" />
              Detaylar yükleniyor...
            </div>
          )}

          <div>
            <h2 className="text-2xl font-bold text-slate-900 leading-tight mb-3">
              {article.ai_title || article.raw_title}
            </h2>
            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
              <span className="font-medium text-slate-700">{article.source_name}</span>
              <span>•</span>
              <span>{new Date(article.scraped_at).toLocaleString("tr-TR")}</span>
              {article.macro_region && (
                <>
                  <span>•</span>
                  <span className="text-indigo-600 font-medium">{article.macro_region}</span>
                </>
              )}
            </div>
          </div>

          {article.extracted_tickers && article.extracted_tickers.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {article.extracted_tickers.map((ticker) => (
                <span
                  key={ticker}
                  className="text-xs font-bold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200"
                >
                  ${ticker}
                </span>
              ))}
            </div>
          )}

          {article.ai_summary && (
            <div className="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-5">
              <div className="flex items-center gap-2 mb-2 text-indigo-900 font-semibold text-sm">
                <Sparkles className="w-4 h-4" />
                AI Özeti
              </div>
              <p className="text-slate-700 text-sm leading-relaxed">{article.ai_summary}</p>
            </div>
          )}

          <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed">
            {paragraphs.map((p, i) => (
              <p key={i} className="mb-4">
                {p}
              </p>
            ))}
            {paragraphs.length === 0 && (
              <p className="text-slate-400 italic">Haber gövdesi bulunamadı.</p>
            )}
          </div>

          <div className="flex flex-wrap gap-3 pt-4 border-t border-slate-100">
            {article.status !== "approved" && article.status !== "rejected" && (
              <>
                <button
                  onClick={() => handleReview(true)}
                  disabled={busy}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition"
                >
                  <ThumbsUp className="w-4 h-4" /> Onayla
                </button>
                <button
                  onClick={() => handleReview(false)}
                  disabled={busy}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 text-white text-sm font-medium hover:bg-rose-700 disabled:opacity-50 transition"
                >
                  <ThumbsDown className="w-4 h-4" /> Reddet
                </button>
              </>
            )}
            {(article.status === "approved" || article.status === "rejected") && (
              <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
                {article.status === "approved" ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Onaylandı
                  </>
                ) : (
                  <>
                    <XCircle className="w-4 h-4 text-rose-600" /> Değerlendirildi
                  </>
                )}
              </div>
            )}
            {!article.ai_summary && (
              <button
                onClick={handleAnalyze}
                disabled={busy}
                className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 disabled:opacity-50 transition"
              >
                <Sparkles className="w-4 h-4" /> AI Analizi Yap
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
