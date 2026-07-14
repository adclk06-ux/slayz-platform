"use client";

import { useState } from "react";
import Link from "next/link";
import { Layers, MessageSquare, TrendingUp } from "lucide-react";
import { Article } from "@/lib/api";
import CategoryVisual from "./CategoryVisual";

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

const MACRO_REGION_LABELS: Record<string, string> = {
  US: "ABD",
  TR: "Türkiye",
  JP: "Japonya",
  EZ: "Euro Bölgesi",
};

const MACRO_INDICATOR_LABELS: Record<string, string> = {
  interest: "Faiz",
  employment: "İstihdam",
  gdp: "Büyüme",
};

function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffMin < 1) return "az önce";
  if (diffMin < 60) return `${diffMin}d önce`;
  if (diffHour < 24) return `${diffHour}s önce`;
  if (diffDay === 1) return "dün";
  return date.toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

function formatClockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

function tradingViewLogoUrl(symbol: string): string {
  // TradingView symbol logos are served from a public CDN path.
  const clean = symbol.replace(/\.IS$/i, "");
  return `https://s3-symbol-logo.tradingview.com/${clean.toLowerCase()}.svg`;
}

function TickerBadge({ symbol }: { symbol: string }) {
  const [error, setError] = useState(false);
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-white border border-slate-200 text-[11px] font-semibold text-slate-700 shadow-sm">
      {!error ? (
        <img
          src={tradingViewLogoUrl(symbol)}
          alt=""
          className="w-3.5 h-3.5 object-contain"
          onError={() => setError(true)}
        />
      ) : (
        <TrendingUp className="w-3.5 h-3.5 text-slate-400" />
      )}
      ${symbol}
    </span>
  );
}

interface ArticleCardProps {
  article: Article;
  onShareToChat?: (article: Article) => void;
  onSelect?: (article: Article) => void;
}

export default function ArticleCard({ article, onShareToChat, onSelect }: ArticleCardProps) {
  const duplicateSources = article.duplicate_source_names || [];

  return (
    <div className="relative">
      <Link
        href={`/article/${article.id}`}
        onClick={(e) => {
          if (onSelect) {
            e.preventDefault();
            onSelect(article);
          }
        }}
        className="glass-card group block rounded-2xl border border-slate-100 p-5 transition-all hover:shadow-lg hover:shadow-slate-200/50 hover:-translate-y-0.5"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="text-[11px] font-semibold uppercase tracking-wide bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full">
                {CATEGORY_LABELS[article.category] || "Genel"}
              </span>
              <span
                className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border ${
                  STATUS_META[article.status]?.className || "bg-slate-50 text-slate-600 border-slate-100"
                }`}
              >
                {STATUS_META[article.status]?.label || "İnceleme Bekliyor"}
              </span>
              {article.macro_region && (
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">
                  {MACRO_REGION_LABELS[article.macro_region] || article.macro_region}
                  {article.macro_indicator ? ` • ${MACRO_INDICATOR_LABELS[article.macro_indicator] || article.macro_indicator}` : ""}
                </span>
              )}
              {article.is_mega_cap && (
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-100 flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" /> Mega-Cap
                </span>
              )}
            </div>

            <h3 className="text-lg font-semibold text-slate-900 leading-snug mb-2 group-hover:text-slate-700">
              {article.ai_title || article.raw_title}
            </h3>

            {article.extracted_tickers && article.extracted_tickers.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {article.extracted_tickers.slice(0, 4).map((ticker) => (
                  <TickerBadge key={ticker} symbol={ticker} />
                ))}
              </div>
            )}

            {article.ai_summary && (
              <p className="text-sm text-slate-500 line-clamp-2">{article.ai_summary}</p>
            )}
            {article.raw_content && (
              <p className="text-sm text-slate-600 line-clamp-3 mt-2">
                {article.raw_content.replace(/\s+/g, " ").trim()}
              </p>
            )}

            <div className="flex items-center flex-wrap gap-2 mt-3 text-xs text-slate-400">
              <span title={new Date(article.scraped_at).toLocaleString("tr-TR")}>
                {formatRelativeTime(article.scraped_at)} • {formatClockTime(article.scraped_at)}
              </span>
              <span className="text-slate-300">|</span>
              <span>{article.source_name}</span>
              {duplicateSources.length > 0 && (
                <>
                  <span className="text-slate-300">|</span>
                  <span className="inline-flex items-center gap-1 text-slate-500" title={duplicateSources.join(", ")}>
                    <Layers className="w-3 h-3" />
                    +{duplicateSources.length} kaynak
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="shrink-0">
            <CategoryVisual category={article.category} sentiment={article.sentiment} size={52} />
          </div>
        </div>
      </Link>

      {onShareToChat && (
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onShareToChat(article);
          }}
          className="absolute bottom-4 right-4 flex items-center gap-1.5 text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1.5 rounded-full transition"
          title="Desk Chat'te Paylaş"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Paylaş
        </button>
      )}
    </div>
  );
}
