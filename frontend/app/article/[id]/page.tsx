"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Article, analyzeArticle, fetchArticle, reviewArticle } from "@/lib/api";
import CategoryVisual from "@/components/CategoryVisual";
import ShareArticleModal from "@/components/ShareArticleModal";
import {
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  XCircle,
} from "lucide-react";

const CATEGORY_LABELS: Record<string, string> = {
  crypto: "Kripto Para",
  stocks: "Borsa",
  commodities: "Emtia / Altın",
  general: "Genel",
};

const STATUS_META: Record<string, { label: string; className: string }> = {
  pending_analysis: { label: "Analiz Hazır", className: "bg-sky-50 text-sky-700 border-sky-100" },
  analyzed: { label: "Analiz Hazır", className: "bg-sky-50 text-sky-700 border-sky-100" },
  pending_review: { label: "İnceleme Bekliyor", className: "bg-amber-50 text-amber-700 border-amber-100" },
  approved: { label: "Onaylandı", className: "bg-emerald-50 text-emerald-700 border-emerald-100" },
  rejected: { label: "Değerlendirildi", className: "bg-slate-50 text-slate-600 border-slate-100" },
  failed: { label: "Analiz Hazır", className: "bg-sky-50 text-sky-700 border-sky-100" },
};

export default function ArticleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = params?.id as string;

  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [showAiSummary, setShowAiSummary] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [autoActionApplied, setAutoActionApplied] = useState(false);

  useEffect(() => {
    const token = window.localStorage.getItem("slayz_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    loadArticle();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    const action = searchParams?.get("action");
    if (article && action && !autoActionApplied && article.status !== "approved" && article.status !== "rejected") {
      setAutoActionApplied(true);
      if (action === "approve") handleReview(true);
      if (action === "reject") handleReview(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [article]);

  async function loadArticle() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchArticle(id);
      setArticle(data);
      setShowAiSummary(!!data.ai_summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bir hata oluştu.");
    } finally {
      setLoading(false);
    }
  }

  async function handleReview(approve: boolean) {
    if (!article) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await reviewArticle(article.id, approve);
      setArticle(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "İşlem başarısız.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAnalyze() {
    if (!article) return;
    setAnalyzing(true);
    setError(null);
    try {
      const updated = await analyzeArticle(article.id);
      setArticle(updated);
      setShowAiSummary(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI analizi başarısız.");
    } finally {
      setAnalyzing(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50/50 flex items-center justify-center text-slate-400 text-sm">
        <div className="flex items-center gap-3">
          <RefreshCw className="w-4 h-4 animate-spin" /> Yükleniyor...
        </div>
      </div>
    );
  }

  if (error && !article) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50/50 px-6">
        <div className="p-4 rounded-xl bg-rose-50 text-rose-600 text-sm border border-rose-100">{error}</div>
      </div>
    );
  }

  if (!article) return null;

  const statusMeta = STATUS_META[article.status] || { label: "İnceleme Bekliyor", className: "bg-amber-50 text-amber-700 border-amber-100" };
  const hasAiSummary = !!article.ai_summary;

  return (
    <div className="min-h-screen bg-slate-50/30">
      <header className="sticky top-0 z-10 border-b border-slate-100 bg-white/80 backdrop-blur-md">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <button
            onClick={() => router.push("/")}
            className="group flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900 transition"
          >
            <span className="p-1.5 rounded-lg border border-slate-100 group-hover:border-slate-200 group-hover:bg-slate-50 transition">
              <ArrowLeft className="w-4 h-4" />
            </span>
            Panele dön
          </button>
          <button
            onClick={() => setShareOpen(true)}
            className="flex items-center gap-2 text-sm font-semibold text-slate-700 bg-white border border-slate-100 hover:border-slate-200 hover:bg-slate-50 px-3.5 py-2 rounded-xl shadow-sm shadow-slate-200/40 transition"
          >
            <Send className="w-3.5 h-3.5" />
            Ekip Arkadaşına Gönder
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        <div className="flex items-center gap-3 mb-6">
          <CategoryVisual category={article.category} sentiment={article.sentiment} size={56} />
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide bg-slate-100 text-slate-600 px-3 py-1 rounded-full w-fit">
              {CATEGORY_LABELS[article.category] || "Genel"}
            </span>
            <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full border w-fit ${statusMeta.className}`}>
              {statusMeta.label}
            </span>
          </div>
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 leading-tight mb-3">
          {article.ai_title || article.raw_title}
        </h1>

        <a
          href={article.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-8 transition"
        >
          {article.source_name} <ExternalLink className="w-3 h-3" />
        </a>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 text-rose-600 text-sm border border-rose-100">{error}</div>
        )}

        <div className="rounded-2xl border border-slate-100 bg-white p-6 sm:p-8 shadow-sm shadow-slate-200/30 mb-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <ExternalLink className="w-5 h-5 text-slate-500" /> Orijinal Haber Metni
            </h2>
            <span className="text-xs text-slate-400">{article.raw_content.length.toLocaleString("tr-TR")} karakter</span>
          </div>
          <div className="prose prose-slate max-w-none">
            {article.raw_content.split("\n").map((paragraph, idx) =>
              paragraph.trim() ? (
                <p key={idx} className="text-slate-700 text-base leading-loose mb-5 last:mb-0">
                  {paragraph}
                </p>
              ) : null
            )}
          </div>
        </div>

        {hasAiSummary && showAiSummary && (
          <div className="rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/60 to-white p-6 sm:p-8 shadow-sm shadow-indigo-100/40 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-white" />
              </div>
              <h2 className="text-sm font-semibold text-indigo-900">AI Özeti & Makro-Mikro Analiz</h2>
            </div>
            <div className="prose prose-slate max-w-none">
              {article.ai_summary!.split("\n").map((paragraph, idx) =>
                paragraph.trim() ? (
                  <p key={idx} className="text-slate-700 leading-relaxed mb-4 last:mb-0">
                    {paragraph}
                  </p>
                ) : null
              )}
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 mb-8">
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-indigo-600 text-white text-sm font-medium shadow-sm shadow-indigo-200/40 hover:bg-indigo-700 hover:shadow-md hover:shadow-indigo-200/40 transition-all disabled:opacity-60"
          >
            {analyzing ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> AI analiz ediyor...
              </>
            ) : hasAiSummary && showAiSummary ? (
              <>
                <RefreshCw className="w-3.5 h-3.5" /> Yeniden Analiz Et
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" /> AI ile Analiz Et
              </>
            )}
          </button>

          <button
            onClick={() => setShareOpen(true)}
            className="flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-white border border-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-50 hover:border-slate-300 shadow-sm shadow-slate-200/30 transition"
          >
            <Send className="w-3.5 h-3.5" /> Ekip Arkadaşına Gönder
          </button>

          <div className="flex-1 min-w-[1px]" />

          <button
            onClick={() => handleReview(true)}
            disabled={submitting || article.status === "approved"}
            className="flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-emerald-600 text-white text-sm font-medium shadow-sm shadow-emerald-200/30 hover:bg-emerald-700 hover:shadow-md hover:shadow-emerald-200/30 transition-all disabled:opacity-50"
          >
            <ThumbsUp className="w-3.5 h-3.5" /> Paylaşmaya Değer
          </button>
          <button
            onClick={() => handleReview(false)}
            disabled={submitting || article.status === "rejected"}
            className="flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-white border border-slate-200 text-slate-700 text-sm font-medium hover:bg-rose-50 hover:border-rose-200 hover:text-rose-700 transition disabled:opacity-50"
          >
            <ThumbsDown className="w-3.5 h-3.5" /> Değmez
          </button>
        </div>

        {article.status === "approved" && (
          <div className="flex items-center justify-center gap-2 mt-5 text-sm text-emerald-600 font-medium">
            <CheckCircle2 className="w-4 h-4" /> Bu haber onaylandı ve paylaşıma hazır.
          </div>
        )}
        {article.status === "rejected" && (
          <div className="flex items-center justify-center gap-2 mt-5 text-sm text-slate-500 font-medium">
            <XCircle className="w-4 h-4" /> Bu haber değerlendirildi ve pas geçildi.
          </div>
        )}
      </main>

      {shareOpen && (
        <ShareArticleModal
          articleId={article.id}
          articleTitle={article.ai_title || article.raw_title}
          onClose={() => setShareOpen(false)}
        />
      )}
    </div>
  );
}
