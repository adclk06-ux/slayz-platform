"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import {
  Article,
  BriefingSnapshot,
  FeedStatus,
  clearAuthSession,
  fetchArticles,
  fetchFeedStatus,
  fetchInboxUnreadCount,
  fetchLatestBriefing,
  runNewsPipeline,
} from "@/lib/api";
import ArticleCard from "@/components/ArticleCard";
import ArticleDetailSheet from "@/components/ArticleDetailSheet";
import InboxPanel from "@/components/InboxPanel";
import ShareToChatModal from "@/components/ShareToChatModal";
import SuggestionToast from "@/components/SuggestionToast";
import { useAuth } from "@/components/AuthProvider";
import {
  Bell,
  Flame,
  Globe,
  Inbox,
  LogOut,
  RefreshCcw,
  ScanSearch,
  Settings,
  Sparkles,
  TrendingUp,
} from "lucide-react";

const CATEGORY_TABS = [
  { value: "", label: "Tümü" },
  { value: "crypto", label: "Kripto Para" },
  { value: "stocks", label: "Borsa" },
  { value: "commodities", label: "Emtia / Altın" },
  { value: "general", label: "Genel" },
  { value: "market", label: "Piyasalar" },
];

const MACRO_REGION_TABS = [
  { value: "", label: "Tüm Bölgeler" },
  { value: "US", label: "ABD" },
  { value: "TR", label: "Türkiye" },
  { value: "JP", label: "Japonya" },
  { value: "EZ", label: "Euro Bölgesi" },
];

export default function DashboardPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [articles, setArticles] = useState<Article[]>([]);
  const articlesRef = useRef<Article[]>([]);
  const [category, setCategory] = useState("");
  const [macroRegion, setMacroRegion] = useState("");
  const [megaCapOnly, setMegaCapOnly] = useState(false);
  const [briefing, setBriefing] = useState<BriefingSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userName, setUserName] = useState<string | null>(null);
  const [feedStatus, setFeedStatus] = useState<FeedStatus | null>(null);
  const [inboxUnread, setInboxUnread] = useState(0);
  const [pipelineRunning, setPipelineRunning] = useState(false);

  // Real-time collaboration UI state
  const [inboxOpen, setInboxOpen] = useState(false);
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [articleToShare, setArticleToShare] = useState<Article | null>(null);
  const [newArticleAlert, setNewArticleAlert] = useState<{ count: number; visible: boolean }>({
    count: 0,
    visible: false,
  });

  useEffect(() => {
    articlesRef.current = articles;
  }, [articles]);

  useEffect(() => {
    setUserName(window.localStorage.getItem("slayz_user_name"));
    loadArticles();
    loadBriefing();
    loadStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, macroRegion, megaCapOnly]);

  useEffect(() => {
    let mounted = true;
    const refreshUnread = () => fetchInboxUnreadCount().then((data) => mounted && setInboxUnread(data.unread_count)).catch(() => undefined);
    refreshUnread();
    const interval = setInterval(refreshUnread, 30000);
    return () => { mounted = false; clearInterval(interval); };
  }, [inboxOpen]);

  // Dakikalık feed auto-refresh
  useEffect(() => {
    if (typeof window === "undefined") return;

    const interval = setInterval(async () => {
      try {
        const fresh = await fetchArticles({
          category: category || undefined,
          macro_region: macroRegion || undefined,
          mega_cap_only: megaCapOnly || undefined,
          primary_only: true,
        });
        const currentIds = new Set(articlesRef.current.map((a) => a.id));
        const incoming = fresh.filter((a) => !currentIds.has(a.id));
        if (incoming.length > 0) {
          setNewArticleAlert({ count: incoming.length, visible: true });
          setTimeout(() => {
            setArticles((prev) => [...incoming, ...prev].slice(0, 200));
            setNewArticleAlert({ count: 0, visible: false });
          }, 3000);
        }
      } catch (err) {
        console.warn("Auto-refresh failed:", err);
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [category, macroRegion, megaCapOnly]);

  async function loadArticles() {
    if (articlesRef.current.length === 0) setLoading(true);
    setError(null);
    try {
      const data = await fetchArticles({
        category: category || undefined,
        macro_region: macroRegion || undefined,
        mega_cap_only: megaCapOnly || undefined,
        primary_only: true,
      });
      // Retain local state if the server returns an empty list while we already have items.
      if (data.length === 0 && articlesRef.current.length > 0) {
        // keep current articles
      } else {
        setArticles(data);
      }
    } catch (err) {
      console.error("Fetch failed:", err);
      setError(err instanceof Error ? err.message : "Bir hata oluştu.");
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadStatus() {
    try { setFeedStatus(await fetchFeedStatus()); } catch { setFeedStatus(null); }
  }

  async function scanSources() {
    setPipelineRunning(true);
    try {
      const result = await runNewsPipeline();
      await Promise.all([loadArticles(), loadBriefing(), loadStatus()]);
      window.alert(`${result.scraped} yeni haber alındı, ${result.analyzed} haber analiz edildi.`);
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Kaynak taraması başlatılamadı.");
    } finally {
      setPipelineRunning(false);
    }
  }

  async function loadBriefing() {
    try {
      const data = await fetchLatestBriefing();
      setBriefing(data);
    } catch (err) {
      console.warn("Briefing not available yet:", err);
      setBriefing(null);
    }
  }

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-slate-100 sticky top-0 bg-white/80 backdrop-blur-md z-10">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative w-10 h-10 rounded-xl overflow-hidden shadow-sm shadow-slate-200/40 border border-slate-100 shrink-0">
              <Image
                src="/images/slayz-logo.webp"
                alt="Slayz Haber Otomasyonu"
                fill
                sizes="40px"
                className="object-contain p-0.5"
                priority
              />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-lg font-bold text-slate-900 leading-tight">Slayz Haber Otomasyonu</h1>
                <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-[10px] font-bold uppercase tracking-wider shadow-sm shadow-indigo-200/50">
                  <Sparkles className="w-3 h-3" />
                  Slayz Co-Pilot
                </span>
              </div>
              <p className="text-xs text-slate-400">Araştırma Bölümü Küratörlük Paneli</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {userName && <span className="text-sm text-slate-500 hidden sm:block mr-1">Merhaba, {userName}</span>}
            <button
              onClick={() => setInboxOpen(true)}
              className="p-2 rounded-xl border border-slate-100 bg-white hover:bg-slate-50 hover:border-slate-200 shadow-sm shadow-slate-200/40 transition relative"
              title="Gelen Kutusu"
            >
              <Inbox className="w-4 h-4 text-slate-500" />
              {inboxUnread > 0 && <span className="absolute -right-1.5 -top-1.5 grid min-h-5 min-w-5 place-items-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">{inboxUnread > 99 ? "99+" : inboxUnread}</span>}
            </button>
            {user?.role === "admin" && (
              <>
                <button disabled={pipelineRunning} onClick={scanSources} className="hidden sm:inline-flex items-center gap-1.5 rounded-xl border border-slate-100 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:border-emerald-100 hover:bg-emerald-50 disabled:opacity-50" title="Gerçek haber kaynaklarını şimdi tara">
                  <ScanSearch className={`w-4 h-4 ${pipelineRunning ? "animate-pulse" : ""}`} /> {pipelineRunning ? "Taranıyor" : "Kaynakları Tara"}
                </button>
                <button onClick={() => router.push("/admin/users")} className="p-2 rounded-xl border border-slate-100 bg-white hover:bg-indigo-50 hover:border-indigo-100 shadow-sm transition" title="Kullanıcı Yönetimi">
                  <Settings className="w-4 h-4 text-slate-500" />
                </button>
              </>
            )}
            <button
              onClick={() => {
                loadArticles();
                loadBriefing();
                loadStatus();
              }}
              className="p-2 rounded-xl border border-slate-100 bg-white hover:bg-slate-50 hover:border-slate-200 shadow-sm shadow-slate-200/40 transition"
              title="Yenile"
            >
              <RefreshCcw className="w-4 h-4 text-slate-500" />
            </button>
            <button
              onClick={handleLogout}
              className="p-2 rounded-xl border border-slate-100 bg-white hover:bg-rose-50 hover:border-rose-100 hover:text-rose-600 shadow-sm shadow-slate-200/40 transition"
              title="Çıkış Yap"
            >
              <LogOut className="w-4 h-4 text-slate-500 group-hover:text-rose-500" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 w-full min-w-0">
        {feedStatus && (
          <div className={`mb-5 flex flex-wrap items-center justify-between gap-2 rounded-xl border px-4 py-3 text-xs ${feedStatus.simulated_articles > 0 ? "border-amber-200 bg-amber-50 text-amber-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
            <span className="font-semibold">{feedStatus.simulated_articles > 0 ? `${feedStatus.simulated_articles} simülasyon kaydı tespit edildi` : "Haber akışı yalnızca gerçek kaynak modunda"}</span>
            <span>{feedStatus.latest_article_at ? `Son haber: ${new Date(feedStatus.latest_article_at).toLocaleString("tr-TR")} · ${feedStatus.latest_source || "Kaynak"}` : "Henüz haber alınmadı; zamanlayıcı yeni kaynakları tarayacak."}</span>
          </div>
        )}
        {/* New article alert */}
        {newArticleAlert.visible && (
          <div className="mb-6 flex items-center justify-between rounded-2xl border border-emerald-100 bg-emerald-50/80 p-4 shadow-sm shadow-emerald-100/40 animate-fade-in">
            <div className="flex items-center gap-3">
              <Bell className="w-5 h-5 text-emerald-600" />
              <span className="text-sm font-semibold text-emerald-800">
                {newArticleAlert.count} yeni haber düştü
              </span>
            </div>
            <button
              onClick={() => {
                loadArticles();
                setNewArticleAlert({ count: 0, visible: false });
              }}
              className="text-sm font-semibold text-emerald-700 hover:text-emerald-900 px-3 py-1.5 rounded-lg bg-white/60 hover:bg-white transition"
            >
              Şimdi Güncelle
            </button>
          </div>
        )}

        {/* Institutional briefing panel */}
        {briefing && (
          <div className="mb-8 rounded-2xl border border-indigo-100 bg-gradient-to-r from-indigo-50/70 to-white p-5 shadow-sm shadow-indigo-100/40">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              <h2 className="text-sm font-bold text-indigo-900 uppercase tracking-wide">
                {briefing.slot} Brifing • {briefing.word_count} kelime
              </h2>
            </div>
            <p className="text-slate-700 text-sm leading-relaxed">{briefing.summary}</p>
          </div>
        )}

        {/* Category filter */}
        <div className="flex gap-2 mb-3 flex-wrap">
          {CATEGORY_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => {
                if (tab.value === "market") {
                  router.push("/terminal");
                } else {
                  setCategory(tab.value);
                }
              }}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium border shadow-sm transition-all ${
                category === tab.value
                  ? "bg-slate-900 text-white border-slate-900 shadow-md shadow-slate-900/10"
                  : "bg-white text-slate-600 border-slate-100 hover:border-slate-200 hover:shadow-md hover:shadow-slate-200/30 hover:text-slate-900"
              }`}
            >
              {tab.value === "market" && <TrendingUp className="w-3.5 h-3.5" />}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Macro region filter */}
        <div className="flex gap-2 mb-3 flex-wrap">
          {MACRO_REGION_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setMacroRegion(tab.value)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border shadow-sm transition-all ${
                macroRegion === tab.value
                  ? "bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-600/10"
                  : "bg-white text-slate-600 border-slate-100 hover:border-slate-200 hover:shadow-md hover:shadow-slate-200/30 hover:text-slate-900"
              }`}
            >
              <Globe className="w-3 h-3" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Mega-cap toggle */}
        <div className="flex items-center gap-2 mb-8">
          <button
            onClick={() => setMegaCapOnly((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border shadow-sm transition-all ${
              megaCapOnly
                ? "bg-amber-50 text-amber-700 border-amber-200"
                : "bg-white text-slate-600 border-slate-100 hover:border-slate-200"
            }`}
          >
            <Flame className={`w-3.5 h-3.5 ${megaCapOnly ? "text-amber-500" : "text-slate-400"}`} />
            {megaCapOnly ? "Mega-Cap Only (> $100B)" : "Tüm Market Cap"}
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-rose-50 text-rose-600 text-sm border border-rose-100">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-slate-400 text-sm py-20 text-center">Yükleniyor...</div>
        ) : articles.length === 0 ? (
          <div className="text-slate-400 text-sm py-20 text-center">Henüz haber bulunmuyor.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {articles.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                onShareToChat={setArticleToShare}
                onSelect={setSelectedArticle}
              />
            ))}
          </div>
        )}
      </main>

      {selectedArticle && (
        <ArticleDetailSheet
          article={selectedArticle}
          onClose={() => setSelectedArticle(null)}
        />
      )}

      <InboxPanel isOpen={inboxOpen} onClose={() => setInboxOpen(false)} />
      <ShareToChatModal article={articleToShare} onClose={() => setArticleToShare(null)} />
      <SuggestionToast />
    </div>
  );
}
