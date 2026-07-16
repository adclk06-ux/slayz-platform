"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  Bot,
  CalendarDays,
  ChevronRight,
  CircleDollarSign,
  LineChart,
  Maximize2,
  Newspaper,
  RefreshCw,
  Search,
  Share2,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Trophy,
  X,
} from "lucide-react";
import Link from "next/link";
import ShareTickerModal from "@/components/ShareTickerModal";
import {
  AIPredictResponse,
  Article,
  DividendEvent,
  fetchArticles,
  ensureNewsFeed,
  fetchArticlesByTicker,
  fetchMarketOverview,
  fetchTickerDetail,
  fetchTickerHistory,
  fetchTickers,
  MarketOverview,
  predictAI,
  Ticker,
  TickerDetail,
  TickerHistoryPoint,
} from "@/lib/api";

type Period = "1d" | "1w" | "1m" | "3m" | "1y" | "5y";
type ChartMode = "line" | "candle";

const PERIODS: { value: Period; label: string }[] = [
  { value: "1d", label: "1G" },
  { value: "1w", label: "1H" },
  { value: "1m", label: "1A" },
  { value: "3m", label: "3A" },
  { value: "1y", label: "1Y" },
  { value: "5y", label: "5Y" },
];

const ASSET_FILTERS = [
  { value: "all", label: "Tümü" },
  { value: "equity", label: "Hisseler" },
  { value: "index", label: "Endeks" },
  { value: "forex", label: "Döviz" },
  { value: "commodity", label: "Emtia" },
  { value: "crypto", label: "Kripto" },
] as const;

function numberValue(value: string | number | null | undefined) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPrice(value: string | number | null | undefined, maximumFractionDigits = 4) {
  const parsed = numberValue(value);
  if (parsed === null) return "—";
  return parsed.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits });
}

function formatCompact(value: number | string | null | undefined) {
  const parsed = numberValue(value);
  if (parsed === null) return "—";
  return new Intl.NumberFormat("tr-TR", { notation: "compact", maximumFractionDigits: 2 }).format(parsed);
}

function formatPercent(value: string | number | null | undefined, fraction = 2) {
  const parsed = numberValue(value);
  if (parsed === null) return "—";
  return `${parsed >= 0 ? "+" : ""}${parsed.toFixed(fraction)}%`;
}

function formatChartTime(ts: number, period: Period) {
  const date = new Date(ts * 1000);
  if (period === "1d") return date.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  if (period === "1w" || period === "1m" || period === "3m") {
    return date.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
  }
  return date.toLocaleDateString("tr-TR", { month: "short", year: "2-digit" });
}

function formatDate(value: string | null) {
  if (!value) return "Tarih açıklanmadı";
  return new Date(`${value}T12:00:00`).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function initials(name: string) {
  return name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function EmptyList({ text }: { text: string }) {
  return <div className="rounded-xl border border-dashed border-slate-200 px-3 py-5 text-center text-xs text-slate-400">{text}</div>;
}

function RadarTickerRow({ ticker, onSelect }: { ticker: Ticker; onSelect: (ticker: Ticker) => void }) {
  const change = numberValue(ticker.change_percent);
  return (
    <button onClick={() => onSelect(ticker)} className="group flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-slate-50">
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-slate-100 text-[10px] font-black text-slate-700">
        {initials(ticker.symbol)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-bold text-slate-950">{ticker.symbol}</span>
          {ticker.reason && <span className="truncate text-[10px] text-slate-400">· {ticker.reason}</span>}
        </div>
        <div className="truncate text-[10px] text-slate-500">{ticker.name}</div>
      </div>
      <div className="text-right">
        <div className="text-xs font-semibold text-slate-900">{formatPrice(ticker.price, 2)}</div>
        <div className={`text-[10px] font-bold ${change === null ? "text-slate-400" : change >= 0 ? "text-emerald-600" : "text-rose-600"}`}>{change === null ? "Veri yok" : formatPercent(change)}</div>
      </div>
      <ChevronRight className="h-3.5 w-3.5 text-slate-300 transition group-hover:translate-x-0.5" />
    </button>
  );
}

function RadarCard({
  title,
  subtitle,
  icon,
  children,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/30">
      <div className="mb-3 flex items-start gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-slate-950 text-white">{icon}</div>
        <div className="min-w-0">
          <h2 className="text-sm font-black text-slate-950">{title}</h2>
          <p className="mt-0.5 text-[10px] leading-4 text-slate-500">{subtitle}</p>
        </div>
      </div>
      <div className="space-y-0.5">{children}</div>
    </section>
  );
}

function DividendRow({ item, ticker, onSelect }: { item: DividendEvent; ticker?: Ticker; onSelect: (ticker: Ticker) => void }) {
  return (
    <button
      disabled={!ticker}
      onClick={() => ticker && onSelect(ticker)}
      className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-slate-50 disabled:cursor-default"
    >
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-amber-50 text-[10px] font-black text-amber-700">{initials(item.symbol)}</div>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-bold text-slate-950">{item.symbol}</div>
        <div className="truncate text-[10px] text-slate-500">{formatDate(item.ex_dividend_date || item.payment_date)}</div>
      </div>
      <div className="text-right">
        <div className="text-xs font-semibold text-slate-900">{item.amount !== null ? `${formatPrice(item.amount, 2)} ${item.currency}` : "Tutar bekleniyor"}</div>
        <div className="text-[10px] text-slate-400">Açıklanmış takvim</div>
      </div>
    </button>
  );
}

function CandlestickCanvas({ points }: { points: TickerHistoryPoint[] }) {
  const candles = points.filter(
    (point) => point.open !== null && point.open !== undefined && point.high !== null && point.high !== undefined && point.low !== null && point.low !== undefined && point.close !== null && point.close !== undefined
  );
  if (candles.length < 2) return <div className="grid h-full place-items-center text-xs text-slate-400">Bu aralıkta mum verisi bulunamadı.</div>;

  const viewWidth = 1000;
  const viewHeight = 330;
  const padding = 24;
  const lows = candles.map((point) => Number(point.low));
  const highs = candles.map((point) => Number(point.high));
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const span = max - min || 1;
  const xStep = (viewWidth - padding * 2) / candles.length;
  const candleWidth = Math.max(1.5, Math.min(9, xStep * 0.55));
  const y = (value: number) => padding + ((max - value) / span) * (viewHeight - padding * 2);

  return (
    <svg viewBox={`0 0 ${viewWidth} ${viewHeight}`} className="h-full w-full" preserveAspectRatio="none" role="img" aria-label="Mum grafik">
      {[0.25, 0.5, 0.75].map((ratio) => (
        <line key={ratio} x1={padding} x2={viewWidth - padding} y1={viewHeight * ratio} y2={viewHeight * ratio} stroke="currentColor" className="text-slate-100" strokeDasharray="4 6" />
      ))}
      {candles.map((point, index) => {
        const open = Number(point.open);
        const high = Number(point.high);
        const low = Number(point.low);
        const close = Number(point.close);
        const positive = close >= open;
        const x = padding + index * xStep + xStep / 2;
        const bodyTop = y(Math.max(open, close));
        const bodyBottom = y(Math.min(open, close));
        const bodyHeight = Math.max(1.5, bodyBottom - bodyTop);
        return (
          <g key={`${point.ts}-${index}`} className={positive ? "text-emerald-500" : "text-rose-500"}>
            <line x1={x} x2={x} y1={y(high)} y2={y(low)} stroke="currentColor" strokeWidth="1.2" />
            <rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} rx="0.8" fill="currentColor" />
          </g>
        );
      })}
    </svg>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-sm font-bold text-slate-900">{value}</div>
    </div>
  );
}

export default function TerminalClient() {
  const searchParams = useSearchParams();
  const focusTicker = searchParams.get("ticker");
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [selected, setSelected] = useState<Ticker | null>(null);
  const [detail, setDetail] = useState<TickerDetail | null>(null);
  const [history, setHistory] = useState<TickerHistoryPoint[]>([]);
  const [tickerNews, setTickerNews] = useState<Article[]>([]);
  const [search, setSearch] = useState("");
  const [assetFilter, setAssetFilter] = useState<(typeof ASSET_FILTERS)[number]["value"]>("all");
  const [period, setPeriod] = useState<Period>("1d");
  const [chartMode, setChartMode] = useState<ChartMode>("line");
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [chartMaximized, setChartMaximized] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiAnswer, setAiAnswer] = useState<AIPredictResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  async function loadMarket() {
    setLoading(true);
    try {
      const [tickerData, overviewData] = await Promise.all([
        fetchTickers(),
        fetchMarketOverview().catch(() => null),
      ]);
      setTickers(tickerData);
      setOverview(overviewData);
      setSelected((current) => {
        const focused = focusTicker ? tickerData.find((ticker) => ticker.symbol.toUpperCase() === focusTicker.toUpperCase()) : undefined;
        const refreshedCurrent = current ? tickerData.find((ticker) => ticker.symbol === current.symbol) : undefined;
        return focused || refreshedCurrent || tickerData.find((ticker) => ticker.category === "equity" && ticker.price) || tickerData[0] || null;
      });
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Piyasa verileri alınamadı.");
    } finally {
      setLoading(false);
    }
  }

  async function loadSelectedData(ticker: Ticker, selectedPeriod: Period) {
    setChartLoading(true);
    try {
      const [historyData, detailData] = await Promise.all([
        fetchTickerHistory(ticker.symbol, selectedPeriod).catch(() => []),
        fetchTickerDetail(ticker.symbol).catch(() => null),
      ]);
      setHistory(historyData);
      setDetail(detailData);
    } finally {
      setChartLoading(false);
    }
  }

  async function loadTickerNews(ticker: Ticker) {
    const term = ticker.symbol.toUpperCase();
    try {
      const [tickerMatches, globalFeed] = await Promise.all([
        fetchArticlesByTicker(ticker.symbol, 20).catch(() => [] as Article[]),
        fetchArticles({ primary_only: true }).catch(() => [] as Article[]),
      ]);
      const keyword = ticker.name.split(/\s+/)[0].toUpperCase();
      const fromGlobal = globalFeed.filter((article) => {
        const haystack = `${article.raw_title} ${article.ai_title || ""} ${(article.extracted_tickers || []).join(" ")}`.toUpperCase();
        return haystack.includes(term) || haystack.includes(keyword);
      });
      const merged = new Map<string, Article>();
      [...tickerMatches, ...fromGlobal].forEach((article) => merged.set(article.id, article));
      let news = Array.from(merged.values()).sort((a, b) => new Date(b.scraped_at).getTime() - new Date(a.scraped_at).getTime());

      if (news.length === 0) {
        const warmup = await ensureNewsFeed().catch(() => null);
        if (warmup?.scheduled || warmup?.refresh_running || !warmup?.has_articles) {
          await new Promise((resolve) => window.setTimeout(resolve, 7000));
          news = await fetchArticlesByTicker(ticker.symbol, 20).catch(() => [] as Article[]);
        }
      }
      setTickerNews(news);
    } catch {
      setTickerNews([]);
    }
  }

  async function askAI(question?: string) {
    if (!selected) return;
    const finalQuestion = (question || aiQuestion || "Bu hisseyi kısa ve orta vadeli risk-getiri açısından değerlendir.").trim();
    setAiQuestion(finalQuestion);
    setAiLoading(true);
    setAiAnswer(null);
    try {
      const answer = await predictAI({
        symbol: selected.symbol,
        question: finalQuestion,
        news_headlines: tickerNews.slice(0, 8).map((article) => article.ai_title || article.raw_title),
      });
      setAiAnswer(answer);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI analizi alınamadı.");
    } finally {
      setAiLoading(false);
    }
  }

  useEffect(() => {
    loadMarket();
    const interval = window.setInterval(loadMarket, 60_000);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selected) return;
    setAiAnswer(null);
    loadSelectedData(selected, period);
    loadTickerNews(selected);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.symbol]);

  useEffect(() => {
    if (!selected) return;
    loadSelectedData(selected, period);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  const filteredTickers = useMemo(() => {
    const needle = search.trim().toLocaleUpperCase("tr-TR");
    return tickers.filter((ticker) => {
      const matchesCategory = assetFilter === "all" || ticker.category === assetFilter;
      const matchesSearch = !needle || `${ticker.symbol} ${ticker.name}`.toLocaleUpperCase("tr-TR").includes(needle);
      return matchesCategory && matchesSearch;
    });
  }, [tickers, search, assetFilter]);

  const tickersBySymbol = useMemo(() => new Map(tickers.map((ticker) => [ticker.symbol, ticker])), [tickers]);
  const chartData = useMemo(() => history.map((point) => ({ ...point, label: formatChartTime(point.ts, period) })), [history, period]);
  const firstPrice = history[0]?.price ?? numberValue(selected?.price) ?? 0;
  const lastPrice = history.at(-1)?.price ?? numberValue(selected?.price) ?? 0;
  const periodChange = firstPrice ? ((lastPrice / firstPrice) - 1) * 100 : numberValue(selected?.change_percent) || 0;
  const positive = periodChange >= 0;
  const chartColor = positive ? "#10b981" : "#f43f5e";
  const historyHigh = history.length ? Math.max(...history.map((point) => point.high ?? point.price)) : null;
  const historyLow = history.length ? Math.min(...history.map((point) => point.low ?? point.price)) : null;
  const canShowCandles = history.some((point) => point.open !== null && point.open !== undefined);

  const chartBody = (
    <div className={`${chartMaximized ? "h-[calc(100vh-180px)]" : "h-[340px]"} mt-4`}>
      {chartLoading ? (
        <div className="grid h-full place-items-center text-sm text-slate-400"><RefreshCw className="mb-2 h-5 w-5 animate-spin" />Grafik yükleniyor...</div>
      ) : history.length === 0 ? (
        <div className="grid h-full place-items-center rounded-2xl border border-dashed border-slate-200 text-center text-sm text-slate-400">
          <div><AlertTriangle className="mx-auto mb-2 h-5 w-5" />Bu zaman aralığında doğrulanmış grafik verisi alınamadı.</div>
        </div>
      ) : chartMode === "candle" && canShowCandles ? (
        <CandlestickCanvas points={history} />
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <defs>
              <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={chartColor} stopOpacity={0.22} />
                <stop offset="100%" stopColor={chartColor} stopOpacity={0.01} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="4 6" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="label" axisLine={false} tickLine={false} minTickGap={40} tick={{ fontSize: 10, fill: "#94a3b8" }} />
            <YAxis domain={["auto", "auto"]} axisLine={false} tickLine={false} width={72} tick={{ fontSize: 10, fill: "#94a3b8" }} tickFormatter={(value) => formatPrice(value, 2)} />
            <Tooltip
              contentStyle={{ borderRadius: 14, border: "1px solid #e2e8f0", boxShadow: "0 12px 30px rgba(15,23,42,.12)", fontSize: 12 }}
              formatter={(value) => [`${formatPrice(value as number)} ${selected?.currency || ""}`, "Fiyat"]}
              labelFormatter={(label) => String(label)}
            />
            <ReferenceLine y={firstPrice} stroke="#cbd5e1" strokeDasharray="3 5" />
            <Area type="monotone" dataKey="price" stroke={chartColor} strokeWidth={2.3} fill="url(#priceFill)" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-slate-950">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link href="/" className="grid h-9 w-9 place-items-center rounded-xl border border-slate-200 bg-white transition hover:bg-slate-50" aria-label="Ana sayfa">
              <ArrowLeft className="h-4 w-4 text-slate-600" />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-black tracking-tight text-slate-950">Piyasalar</h1>
                <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-[9px] font-black uppercase tracking-widest text-indigo-700">
                  <Sparkles className="h-2.5 w-2.5" /> Slayz Intelligence
                </span>
              </div>
              <p className="text-[10px] text-slate-400">Gerçek veri · ekip paylaşımı · temellendirilmiş AI</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {lastUpdated && <span className="hidden text-[10px] text-slate-400 md:inline">Güncellendi {lastUpdated.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</span>}
            <button onClick={loadMarket} disabled={loading} className="grid h-9 w-9 place-items-center rounded-xl border border-slate-200 bg-white transition hover:bg-slate-50 disabled:opacity-50" title="Yenile">
              <RefreshCw className={`h-4 w-4 text-slate-600 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1500px] space-y-6 px-4 py-6 sm:px-6">
        {error && (
          <div className="flex items-start justify-between rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            <span>{error}</span><button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
          </div>
        )}

        <section>
          <div className="mb-3 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-lg font-black tracking-tight text-slate-950">Piyasa Radarı</h2>
              <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">Savaş sepetleri sektör hassasiyeti izleme listesidir; gerçekleşmiş kazanç/kayıp veya yatırım tavsiyesi değildir. Günün yükselenleri yalnızca gerçek sağlayıcı verisinden hesaplanır.</p>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <RadarCard title="Savaşın Kazananları" subtitle="Savunma, enerji ve güvenli liman hassasiyeti" icon={<Trophy className="h-4 w-4" />}>
              {overview?.war_winners?.length ? overview.war_winners.slice(0, 5).map((ticker) => <RadarTickerRow key={ticker.symbol} ticker={ticker} onSelect={setSelected} />) : <EmptyList text="Tematik hisseler henüz yüklenmedi." />}
            </RadarCard>
            <RadarCard title="Savaşın Kaybedenleri" subtitle="Yakıt, rota, talep ve tedarik zinciri riski" icon={<ShieldAlert className="h-4 w-4" />}>
              {overview?.war_losers?.length ? overview.war_losers.slice(0, 5).map((ticker) => <RadarTickerRow key={ticker.symbol} ticker={ticker} onSelect={setSelected} />) : <EmptyList text="Tematik hisseler henüz yüklenmedi." />}
            </RadarCard>
            <RadarCard title="Bugün En Çok Yükselenler" subtitle="Simülasyon hariç gün içi yüzde değişim" icon={<TrendingUp className="h-4 w-4" />}>
              {overview?.top_gainers?.length ? overview.top_gainers.slice(0, 5).map((ticker) => <RadarTickerRow key={ticker.symbol} ticker={ticker} onSelect={setSelected} />) : <EmptyList text="Canlı BIST verisi alınamadığı için sıralama yapılmadı." />}
            </RadarCard>
            <RadarCard title="Yakında Temettü Dağıtacaklar" subtitle="Sağlayıcıda açıklanmış yaklaşan tarihler" icon={<CalendarDays className="h-4 w-4" />}>
              {overview?.upcoming_dividends?.length ? overview.upcoming_dividends.slice(0, 5).map((item) => <DividendRow key={`${item.symbol}-${item.ex_dividend_date}`} item={item} ticker={tickersBySymbol.get(item.symbol)} onSelect={setSelected} />) : <EmptyList text="Açıklanmış canlı temettü takvimi alınamadı." />}
            </RadarCard>
          </div>
        </section>

        <section className="grid min-h-[780px] gap-5 xl:grid-cols-[330px_minmax(0,1fr)]">
          <aside className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 p-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Hisse veya varlık ara" className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-3 text-sm outline-none transition focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-50" />
              </div>
              <div className="mt-3 flex gap-1 overflow-x-auto pb-1">
                {ASSET_FILTERS.map((filter) => (
                  <button key={filter.value} onClick={() => setAssetFilter(filter.value)} className={`whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[10px] font-bold transition ${assetFilter === filter.value ? "bg-slate-950 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200"}`}>{filter.label}</button>
                ))}
              </div>
            </div>
            <div className="max-h-[700px] overflow-y-auto p-2">
              {filteredTickers.map((ticker) => {
                const change = numberValue(ticker.change_percent);
                const active = selected?.symbol === ticker.symbol;
                return (
                  <button key={ticker.symbol} onClick={() => setSelected(ticker)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition ${active ? "bg-indigo-50 ring-1 ring-indigo-100" : "hover:bg-slate-50"}`}>
                    <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-full text-[10px] font-black ${active ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"}`}>{initials(ticker.symbol)}</div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5"><span className="text-xs font-black text-slate-950">{ticker.symbol}</span>{ticker.is_simulated && <span className="rounded bg-amber-100 px-1 py-0.5 text-[8px] font-bold text-amber-700">DEMO</span>}</div>
                      <div className="truncate text-[10px] text-slate-400">{ticker.name}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-semibold text-slate-900">{formatPrice(ticker.price, 2)}</div>
                      <div className={`text-[10px] font-bold ${change === null ? "text-slate-400" : change >= 0 ? "text-emerald-600" : "text-rose-600"}`}>{change === null ? "—" : formatPercent(change)}</div>
                    </div>
                  </button>
                );
              })}
              {!filteredTickers.length && <EmptyList text="Aramanla eşleşen varlık bulunamadı." />}
            </div>
          </aside>

          <div className="min-w-0 space-y-5">
            {selected ? (
              <>
                <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
                  <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
                    <div>
                      <div className="flex items-center gap-3">
                        <div className="grid h-12 w-12 place-items-center rounded-full bg-slate-950 text-xs font-black text-white">{initials(selected.symbol)}</div>
                        <div>
                          <div className="flex items-center gap-2"><h2 className="text-sm font-black text-slate-950">{selected.name}</h2><span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold text-slate-500">{selected.symbol}</span></div>
                          <div className="mt-0.5 flex items-center gap-2 text-[10px] text-slate-400"><span>{detail?.exchange || "Piyasa"}</span><span>·</span><span className={selected.source === "yahoo" || selected.source === "yahoo (derived)" ? "text-emerald-600" : "text-amber-600"}>Kaynak: {selected.source || "bekleniyor"}</span></div>
                        </div>
                      </div>
                      <div className="mt-5 flex flex-wrap items-end gap-x-4 gap-y-2">
                        <div className="text-4xl font-black tracking-tight text-slate-950">{formatPrice(lastPrice || selected.price)} <span className="text-base font-bold text-slate-400">{selected.currency}</span></div>
                        <div className={`mb-1 flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-black ${positive ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>{positive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}{formatPercent(periodChange)}</div>
                      </div>
                      <p className="mt-2 text-[10px] text-slate-400">Seçili dönem performansı · {PERIODS.find((item) => item.value === period)?.label}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => setShareOpen(true)} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 transition hover:bg-slate-50"><Share2 className="h-4 w-4" /> Ekip arkadaşına gönder</button>
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                    <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1">
                      {PERIODS.map((item) => <button key={item.value} onClick={() => setPeriod(item.value)} className={`rounded-lg px-3 py-1.5 text-[10px] font-black transition ${period === item.value ? "bg-white text-slate-950 shadow-sm" : "text-slate-500 hover:text-slate-900"}`}>{item.label}</button>)}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex rounded-xl border border-slate-200 p-1">
                        <button onClick={() => setChartMode("line")} className={`grid h-7 w-8 place-items-center rounded-lg ${chartMode === "line" ? "bg-slate-950 text-white" : "text-slate-400"}`} title="Çizgi grafik"><LineChart className="h-3.5 w-3.5" /></button>
                        <button onClick={() => setChartMode("candle")} disabled={!canShowCandles} className={`grid h-7 w-8 place-items-center rounded-lg disabled:opacity-30 ${chartMode === "candle" ? "bg-slate-950 text-white" : "text-slate-400"}`} title="Mum grafik"><BarChart3 className="h-3.5 w-3.5" /></button>
                      </div>
                      <button onClick={() => setChartMaximized(true)} className="grid h-9 w-9 place-items-center rounded-xl border border-slate-200 text-slate-500 hover:bg-slate-50" title="Grafiği büyüt"><Maximize2 className="h-4 w-4" /></button>
                    </div>
                  </div>
                  {chartBody}

                  <div className="mt-5 grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-6">
                    <Metric label="Açılış" value={formatPrice(detail?.open)} />
                    <Metric label="Dönem En Yüksek" value={formatPrice(historyHigh)} />
                    <Metric label="Dönem En Düşük" value={formatPrice(historyLow)} />
                    <Metric label="52H Yüksek" value={formatPrice(detail?.fifty_two_week_high)} />
                    <Metric label="52H Düşük" value={formatPrice(detail?.fifty_two_week_low)} />
                    <Metric label="Hacim" value={formatCompact(detail?.volume)} />
                  </div>
                </section>

                <section className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(330px,.8fr)]">
                  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white"><Bot className="h-5 w-5" /></div><div><h3 className="text-sm font-black text-slate-950">Slayz AI Hisse Analizi</h3><p className="mt-0.5 text-[10px] leading-4 text-slate-500">Doğrulanmış fiyatlar, hesaplanan teknik metrikler ve son haberlerle gerekçeli analiz</p></div></div>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-[9px] font-bold text-slate-500">Yatırım tavsiyesi değildir</span>
                    </div>

                    {!aiAnswer && !aiLoading && (
                      <>
                        <div className="mt-5 grid gap-2 sm:grid-cols-3">
                          {["Kısa ve orta vadeli görünümü analiz et", "En önemli riskleri açıkla", "Teknik seviyeleri ve haber etkisini değerlendir"].map((question) => <button key={question} onClick={() => askAI(question)} className="rounded-xl border border-slate-200 px-3 py-3 text-left text-[11px] font-semibold leading-4 text-slate-600 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-800">{question}</button>)}
                        </div>
                        <div className="mt-3 flex gap-2"><input value={aiQuestion} onChange={(event) => setAiQuestion(event.target.value)} onKeyDown={(event) => event.key === "Enter" && askAI()} placeholder={`${selected.symbol} hakkında soru sor...`} className="min-w-0 flex-1 rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50" /><button onClick={() => askAI()} className="rounded-xl bg-slate-950 px-4 text-xs font-bold text-white hover:bg-slate-800">Analiz et</button></div>
                      </>
                    )}

                    {aiLoading && <div className="mt-5 flex items-center gap-3 rounded-2xl bg-indigo-50 px-4 py-5 text-sm text-indigo-700"><RefreshCw className="h-5 w-5 animate-spin" /><div><div className="font-bold">Veriler kontrol ediliyor</div><div className="text-xs text-indigo-500">Teknik metrikler ve haber bağlamı hazırlanıyor...</div></div></div>}

                    {aiAnswer && (
                      <div className="mt-5 space-y-4">
                        <div className="rounded-2xl border border-indigo-100 bg-indigo-50/70 p-4">
                          <div className="mb-2 flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-[10px] font-black ${aiAnswer.stance === "pozitif" ? "bg-emerald-100 text-emerald-700" : aiAnswer.stance === "negatif" ? "bg-rose-100 text-rose-700" : "bg-slate-200 text-slate-700"}`}>{aiAnswer.stance.toLocaleUpperCase("tr-TR")}</span><span className="text-[10px] font-semibold text-slate-500">Güven: {aiAnswer.confidence}</span></div>
                          <p className="text-sm font-medium leading-6 text-slate-800">{aiAnswer.summary}</p>
                        </div>
                        <div><h4 className="mb-2 flex items-center gap-2 text-xs font-black text-slate-900"><Activity className="h-4 w-4 text-indigo-600" /> Teknik görünüm</h4><p className="text-xs leading-5 text-slate-600">{aiAnswer.technical_view}</p></div>
                        <div className="grid gap-4 sm:grid-cols-2">
                          <div><h4 className="mb-2 text-xs font-black text-emerald-700">Olumlu katalizörler</h4>{aiAnswer.catalysts.length ? <ul className="space-y-2">{aiAnswer.catalysts.map((item) => <li key={item} className="flex gap-2 text-xs leading-5 text-slate-600"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />{item}</li>)}</ul> : <p className="text-xs text-slate-400">Belirgin katalizör bulunamadı.</p>}</div>
                          <div><h4 className="mb-2 text-xs font-black text-rose-700">Başlıca riskler</h4>{aiAnswer.risks.length ? <ul className="space-y-2">{aiAnswer.risks.map((item) => <li key={item} className="flex gap-2 text-xs leading-5 text-slate-600"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" />{item}</li>)}</ul> : <p className="text-xs text-slate-400">Belirgin risk listelenmedi.</p>}</div>
                        </div>
                        <div className="rounded-xl bg-slate-50 p-3 text-[10px] leading-4 text-slate-500"><strong className="text-slate-700">Veri kalitesi:</strong> {aiAnswer.data_quality}<br />{aiAnswer.disclaimer}</div>
                        <div className="flex justify-end"><button onClick={() => setShareOpen(true)} className="inline-flex items-center gap-2 rounded-xl border border-indigo-200 px-3 py-2 text-xs font-bold text-indigo-700 hover:bg-indigo-50"><Share2 className="h-3.5 w-3.5" /> Analizle birlikte paylaş</button></div>
                      </div>
                    )}
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center justify-between"><div><h3 className="flex items-center gap-2 text-sm font-black text-slate-950"><CircleDollarSign className="h-4 w-4 text-indigo-600" /> Hisse İstatistikleri</h3><p className="mt-1 text-[10px] text-slate-400">Sağlayıcıda mevcut temel piyasa bilgileri</p></div></div>
                    <div className="mt-4 grid grid-cols-2 gap-2">
                      <Metric label="Piyasa Değeri" value={formatCompact(detail?.market_cap)} />
                      <Metric label="F/K" value={formatPrice(detail?.trailing_pe, 2)} />
                      <Metric label="PD/DD" value={formatPrice(detail?.price_to_book, 2)} />
                      <Metric label="Temettü Verimi" value={detail?.dividend_yield ? formatPercent(detail.dividend_yield * 100) : "—"} />
                      <Metric label="Önceki Kapanış" value={formatPrice(detail?.previous_close)} />
                      <Metric label="Ort. Hacim" value={formatCompact(detail?.average_volume)} />
                    </div>
                  </div>
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="mb-4 flex items-center justify-between"><div><h3 className="flex items-center gap-2 text-sm font-black text-slate-950"><Newspaper className="h-4 w-4 text-indigo-600" /> {selected.symbol} Haberleri</h3><p className="mt-1 text-[10px] text-slate-400">Platformun gerçek haber akışından hisseyle eşleşen içerikler</p></div><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-500">{tickerNews.length} haber</span></div>
                  {tickerNews.length ? <div className="grid gap-3 md:grid-cols-2">{tickerNews.slice(0, 8).map((article) => <Link key={article.id} href={`/article/${article.id}`} className="rounded-xl border border-slate-100 p-4 transition hover:border-indigo-100 hover:bg-indigo-50/40"><div className="mb-2 flex items-center justify-between gap-3 text-[9px] font-semibold uppercase tracking-wide text-slate-400"><span>{article.source_name}</span><span>{new Date(article.scraped_at).toLocaleDateString("tr-TR")}</span></div><h4 className="line-clamp-2 text-xs font-bold leading-5 text-slate-900">{article.ai_title || article.raw_title}</h4>{article.ai_summary && <p className="mt-2 line-clamp-2 text-[10px] leading-4 text-slate-500">{article.ai_summary}</p>}</Link>)}</div> : <EmptyList text="Bu hisseyle eşleşen güncel haber bulunamadı." />}
                </section>
              </>
            ) : <div className="grid h-full place-items-center rounded-2xl border border-dashed border-slate-200 bg-white text-sm text-slate-400">Bir varlık seç.</div>}
          </div>
        </section>
      </main>

      {chartMaximized && selected && (
        <div className="fixed inset-0 z-[70] bg-white p-5 sm:p-8">
          <div className="flex items-center justify-between"><div><h2 className="text-lg font-black">{selected.symbol} · {selected.name}</h2><p className="text-xs text-slate-400">{PERIODS.find((item) => item.value === period)?.label} grafik</p></div><button onClick={() => setChartMaximized(false)} className="grid h-10 w-10 place-items-center rounded-xl border border-slate-200 hover:bg-slate-50"><X className="h-4 w-4" /></button></div>
          {chartBody}
        </div>
      )}

      <ShareTickerModal ticker={shareOpen ? selected : null} analysis={aiAnswer} onClose={() => setShareOpen(false)} />
    </div>
  );
}
