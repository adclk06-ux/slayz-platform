// Empty API base URL means same-origin requests, proxied to the backend via
// next.config.js rewrites in development. This keeps the httpOnly
// refresh-token cookie first-party so silent session refresh works.
export const API_BASE_URL = "";

const rawWsUrl = process.env.NEXT_PUBLIC_WS_URL;
// May be empty when API_BASE_URL is same-origin; consumers must fall back to
// window.location.origin at call time (WebSocket requires an absolute URL).
export const WS_BASE_URL = rawWsUrl
  ? rawWsUrl.replace(/\/$/, "")
  : API_BASE_URL.replace(/^http/, (scheme) => (scheme === "https" ? "wss" : "ws"));

export type ArticleStatus =
  | "pending_analysis"
  | "analyzed"
  | "pending_review"
  | "approved"
  | "rejected"
  | "failed";

export type NewsCategory = "crypto" | "stocks" | "commodities" | "general";
export type MacroRegion = "US" | "TR" | "JP" | "EZ";
export type MacroIndicator = "interest" | "employment" | "gdp";

export interface Article {
  id: string;
  source_name: string;
  source_url: string;
  category: NewsCategory;
  raw_title: string;
  raw_content: string;
  ai_title: string | null;
  ai_summary: string | null;
  sentiment: string | null;
  status: ArticleStatus;
  email_sent: boolean;
  scraped_at: string;
  analyzed_at: string | null;

  // Institutional-grade enrichment fields
  extracted_tickers: string[] | null;
  market_cap_usd: string | null;
  is_mega_cap: boolean;
  macro_region: MacroRegion | null;
  macro_indicator: MacroIndicator | null;
  duplicate_group_id: string | null;
  is_primary_duplicate: boolean;
  duplicate_source_names: string[] | null;
}

export interface BriefingSnapshot {
  id: string;
  created_at: string;
  slot: string;
  article_ids: string[];
  summary: string;
  word_count: number;
}

const AUTH_COOKIE_NAME = "slayz_authenticated";

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("slayz_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Persists the JWT + user info in localStorage (used for Authorization headers)
 * and sets a lightweight, non-sensitive presence cookie so the edge middleware
 * (middleware.ts) can redirect unauthenticated users before any client JS runs.
 */
export function setAuthSession(accessToken: string, fullName: string) {
  window.localStorage.setItem("slayz_token", accessToken);
  window.localStorage.setItem("slayz_user_name", fullName);
  document.cookie = `${AUTH_COOKIE_NAME}=1; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
  window.dispatchEvent(new CustomEvent("slayz-token-updated", { detail: { accessToken } }));
}

export function clearAuthSession() {
  window.localStorage.removeItem("slayz_token");
  window.localStorage.removeItem("slayz_user_name");
  document.cookie = `${AUTH_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
}

async function sleep(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

class HttpStatusError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function apiFetch<T>(url: string, options: RequestInit = {}, allowRefresh = true): Promise<T> {
  let lastError: unknown = null;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 30000);
      const res = await fetch(url, {
        ...options,
        signal: options.signal || controller.signal,
        headers: { ...authHeaders(), ...(options.headers || {}) },
        credentials: "include",
        cache: "no-store",
      });
      clearTimeout(timer);

      if (res.status === 401 && allowRefresh) {
        const session = await refreshSession();
        setAuthSession(session.access_token, session.full_name);
        return apiFetch<T>(url, options, false);
      }
      if ([502, 503, 504].includes(res.status) && attempt < 4) {
        await sleep(1200 * (attempt + 1));
        continue;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new HttpStatusError(res.status, body?.detail || `İstek başarısız (${res.status}).`);
      }
      return res.json();
    } catch (err) {
      lastError = err;
      if (err instanceof HttpStatusError) {
        if ((err.status === 401 || err.status === 403) && allowRefresh) throw err;
        if (![502, 503, 504].includes(err.status)) throw err;
      }
      if (attempt < 4) {
        await sleep(1200 * (attempt + 1));
        continue;
      }
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Sunucuya ulaşılamadı. Lütfen tekrar deneyin.");
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Giriş başarısız." }));
    throw new Error(err.detail || "Giriş başarısız.");
  }
  return res.json();
}

export interface AuthUser {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  avatar_url: string | null;
  status: string;
  last_seen_at: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SetupStatus {
  needs_setup: boolean;
  allowed_email_domain: string;
}

export async function fetchSetupStatus(): Promise<SetupStatus> {
  const res = await fetch(`${API_BASE_URL}/api/auth/setup-status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Kurulum durumu alınamadı.");
  return res.json();
}

export async function bootstrapAdmin(payload: {
  full_name: string;
  email: string;
  password: string;
}): Promise<AuthUser> {
  const res = await fetch(`${API_BASE_URL}/api/auth/bootstrap-admin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, role: "admin" }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || "Yönetici hesabı oluşturulamadı.");
  return body;
}

export async function getCurrentUser(): Promise<AuthUser> {
  return apiFetch<AuthUser>(`${API_BASE_URL}/api/auth/me`);
}

export async function refreshSession(): Promise<{ access_token: string; role: string; full_name: string }> {
  const res = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Oturum yenilenemedi." }));
    throw new Error(body.detail || "Oturum yenilenemedi.");
  }
  return res.json();
}

export async function fetchAdminUsers(): Promise<AuthUser[]> {
  return apiFetch<AuthUser[]>(`${API_BASE_URL}/api/admin/users`);
}

export async function createAdminUser(payload: {
  full_name: string;
  email: string;
  password: string;
  role: string;
}): Promise<AuthUser> {
  return apiFetch<AuthUser>(`${API_BASE_URL}/api/admin/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateAdminUser(
  userId: string,
  payload: { full_name?: string; role?: string; is_active?: boolean; password?: string }
): Promise<AuthUser> {
  return apiFetch<AuthUser>(`${API_BASE_URL}/api/admin/users/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deactivateAdminUser(userId: string): Promise<AuthUser> {
  return apiFetch<AuthUser>(`${API_BASE_URL}/api/admin/users/${userId}`, { method: "DELETE" });
}

export async function logout(): Promise<void> {
  await apiFetch(`${API_BASE_URL}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export interface ArticleFilters {
  category?: string;
  status?: string;
  mega_cap_only?: boolean;
  macro_region?: string;
  macro_indicator?: string;
  primary_only?: boolean;
}

export async function fetchArticles(params?: ArticleFilters): Promise<Article[]> {
  const query = new URLSearchParams();
  if (params?.category) query.set("category", params.category);
  if (params?.status) query.set("status_filter", params.status);
  if (params?.mega_cap_only) query.set("mega_cap_only", "true");
  if (params?.macro_region) query.set("macro_region", params.macro_region);
  if (params?.macro_indicator) query.set("macro_indicator", params.macro_indicator);
  if (params?.primary_only) query.set("primary_only", "true");
  return apiFetch<Article[]>(`${API_BASE_URL}/api/articles?${query.toString()}`);
}

export async function fetchLatestBriefing(): Promise<BriefingSnapshot> {
  return apiFetch<BriefingSnapshot>(`${API_BASE_URL}/api/articles/briefings/latest`);
}

export async function fetchBriefings(limit = 10): Promise<BriefingSnapshot[]> {
  return apiFetch<BriefingSnapshot[]>(`${API_BASE_URL}/api/articles/briefings?limit=${limit}`);
}

// --- Inbox ---

export interface InboxMessage {
  id: string;
  sender_id: string;
  recipient_id: string;
  sender_name: string;
  sender_avatar: string | null;
  title: string;
  content: string;
  associated_ticker: string | null;
  is_read: boolean;
  created_at: string;
}

export async function fetchInbox(unreadOnly = false): Promise<InboxMessage[]> {
  const qs = unreadOnly ? "?unread_only=true" : "";
  return apiFetch<InboxMessage[]>(`${API_BASE_URL}/api/inbox${qs}`);
}

export async function fetchInboxUnreadCount(): Promise<{ unread_count: number }> {
  return apiFetch<{ unread_count: number }>(`${API_BASE_URL}/api/inbox/unread-count`);
}

export async function createInboxMessage(message: {
  recipient_id: string;
  title: string;
  content: string;
  associated_ticker?: string;
}): Promise<InboxMessage> {
  return apiFetch<InboxMessage>(`${API_BASE_URL}/api/inbox`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(message),
  });
}

export async function markInboxAsRead(messageId: string): Promise<InboxMessage> {
  return apiFetch<InboxMessage>(`${API_BASE_URL}/api/inbox/${messageId}/read`, {
    method: "POST",
  });
}

export async function markAllInboxAsRead(): Promise<{ detail: string }> {
  return apiFetch<{ detail: string }>(`${API_BASE_URL}/api/inbox/mark-all-read`, {
    method: "POST",
  });
}

// --- Team Chat ---

export interface ChatMessageSender {
  id: string;
  full_name: string;
  email: string;
  avatar_url: string | null;
  status: string;
}

export interface ChatMessage {
  id: string;
  room_id: string;
  content: string | null;
  message_type: "text" | "image" | "file" | "system";
  created_at: string;
  edited_at: string | null;
  sender: ChatMessageSender;
  attachments: { file_name: string; file_url: string; mime_type: string }[];
}

export interface TeamChatMessage {
  type?: "message" | "chat" | "system";
  id?: string;
  sender_id?: string;
  sender_name: string;
  recipient_id?: string | null;
  content: string;
  article_id?: string | null;
  article_title?: string | null;
  ticker?: string | null;
  created_at?: string;
}

export interface RoomMemberUser {
  id: string;
  full_name: string;
  email: string;
  avatar_url: string | null;
  status: string;
  is_online: boolean;
}

export interface LastMessage {
  id: string;
  content: string | null;
  created_at: string;
  sender: RoomMemberUser;
}

export interface Room {
  id: string;
  name: string | null;
  type: "direct" | "group";
  avatar_url: string | null;
  members: RoomMemberUser[];
  last_message: LastMessage | null;
  unread_count: number;
  updated_at: string;
}

export interface ChatUser {
  id: string;
  full_name: string;
  role: string;
  avatar_url: string | null;
  status: string;
  is_online: boolean;
  last_message: string | null;
  last_message_at: string | null;
}

export async function fetchChatUsers(): Promise<ChatUser[]> {
  return apiFetch<ChatUser[]>(`${API_BASE_URL}/api/chat/users`);
}

export async function fetchRooms(): Promise<Room[]> {
  return apiFetch<Room[]>(`${API_BASE_URL}/api/rooms`);
}

export async function fetchRoomMessages(
  roomId: string,
  options: { limit?: number; beforeId?: string } = {}
): Promise<{ messages: ChatMessage[]; next_cursor?: string; has_more: boolean }> {
  const qs = new URLSearchParams();
  if (options.limit) qs.set("limit", String(options.limit));
  if (options.beforeId) qs.set("before_id", options.beforeId);
  return apiFetch<{ messages: ChatMessage[]; next_cursor?: string; has_more: boolean }>(
    `${API_BASE_URL}/api/rooms/${roomId}/messages?${qs.toString()}`
  );
}

export async function sendRoomMessage(roomId: string, content: string): Promise<ChatMessage> {
  return apiFetch<ChatMessage>(`${API_BASE_URL}/api/rooms/${roomId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function markRoomRead(roomId: string, messageId: string): Promise<void> {
  await apiFetch(`${API_BASE_URL}/api/rooms/${roomId}/read?message_id=${encodeURIComponent(messageId)}`, {
    method: "POST",
  });
}

export interface FeedStatus {
  total_articles: number;
  live_articles: number;
  simulated_articles: number;
  latest_article_at: string | null;
  latest_source: string | null;
  is_live_only: boolean;
}

export async function fetchFeedStatus(): Promise<FeedStatus> {
  return apiFetch<FeedStatus>(`${API_BASE_URL}/api/articles/feed-status`);
}

export async function runNewsPipeline(): Promise<{ scraped: number; analyzed: number; emailed: number }> {
  return apiFetch(`${API_BASE_URL}/api/articles/pipeline/run`, { method: "POST" });
}

export async function createRoom(payload: {
  type: "direct" | "group";
  name?: string;
  member_ids: string[];
}): Promise<Room> {
  return apiFetch<Room>(`${API_BASE_URL}/api/rooms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchChatHistory(limit = 100, peerId?: string): Promise<TeamChatMessage[]> {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (peerId) qs.set("peer_id", peerId);
  return apiFetch<TeamChatMessage[]>(`${API_BASE_URL}/api/chat/history?${qs.toString()}`);
}

export async function fetchArticle(id: string): Promise<Article> {
  return apiFetch<Article>(`${API_BASE_URL}/api/articles/${id}`);
}

export async function fetchArticlesByTicker(symbol: string, limit = 50): Promise<Article[]> {
  return apiFetch<Article[]>(
    `${API_BASE_URL}/api/articles/by-ticker/${encodeURIComponent(symbol)}?limit=${limit}`
  );
}

export async function reviewArticle(id: string, approve: boolean): Promise<Article> {
  const res = await fetch(`${API_BASE_URL}/api/articles/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ approve }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "İşlem başarısız." }));
    throw new Error(err.detail || "İşlem başarısız.");
  }
  return res.json();
}

export async function analyzeArticle(id: string): Promise<Article> {
  const res = await fetch(`${API_BASE_URL}/api/articles/${id}/analyze`, {
    method: "POST",
    headers: { ...authHeaders() },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "AI analizi başarısız." }));
    throw new Error(err.detail || "AI analizi başarısız.");
  }
  return res.json();
}

export async function shareArticle(articleId: string, email: string, note?: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/articles/${articleId}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ email, note: note || undefined }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Haber gönderilemedi." }));
    throw new Error(err.detail || "Haber gönderilemedi.");
  }
}

export interface AssistantChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
  action?: { type: string; symbol?: string; route?: string } | null;
}

export async function chatWithAssistant(messages: AssistantChatMessage[]): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/api/assistant/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ messages }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "AI asistanına ulaşılamadı." }));
    throw new Error(err.detail || "AI asistanına ulaşılamadı.");
  }
  return res.json();
}

// --- Market / Terminal ---

export interface Ticker {
  id: string;
  symbol: string;
  name: string;
  category: "index" | "commodity" | "equity" | "crypto" | "forex";
  price: string | null;
  change: string | null;
  change_percent: string | null;
  currency: string | null;
  source: string | null;
  is_simulated: boolean;
  last_updated: string | null;
  reason?: string | null;
}

export interface TickerHistoryPoint {
  ts: number;
  price: number;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
}

export interface DividendEvent {
  symbol: string;
  name: string;
  ex_dividend_date: string | null;
  payment_date: string | null;
  amount: number | null;
  currency: string;
  source: string;
}

export interface MarketOverview {
  generated_at: string;
  real_data_only: boolean;
  methodology: string;
  war_winners: Ticker[];
  war_losers: Ticker[];
  top_gainers: Ticker[];
  upcoming_dividends: DividendEvent[];
  dividend_status: "live" | "unavailable" | string;
}

export interface TickerDetail {
  symbol: string;
  name: string;
  price: string | null;
  change: string | null;
  change_percent: string | null;
  currency: string | null;
  last_updated: string | null;
  is_simulated: boolean;
  quote_status: string;
  market_cap?: number | null;
  previous_close?: number | null;
  open?: number | null;
  day_high?: number | null;
  day_low?: number | null;
  fifty_two_week_high?: number | null;
  fifty_two_week_low?: number | null;
  volume?: number | null;
  average_volume?: number | null;
  trailing_pe?: number | null;
  price_to_book?: number | null;
  dividend_yield?: number | null;
  exchange?: string | null;
  source?: string | null;
}

export async function fetchTickers(category?: string): Promise<Ticker[]> {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  return apiFetch<Ticker[]>(`${API_BASE_URL}/api/market/tickers${qs}`);
}

export async function fetchMarketOverview(): Promise<MarketOverview> {
  return apiFetch<MarketOverview>(`${API_BASE_URL}/api/market/overview`);
}

export async function fetchTickerDetail(symbol: string): Promise<TickerDetail> {
  return apiFetch<TickerDetail>(`${API_BASE_URL}/api/market/tickers/${encodeURIComponent(symbol)}/detail`);
}

export async function fetchTickerHistory(
  symbol: string,
  period: "1d" | "1w" | "1m" | "3m" | "1y" | "5y" = "1d"
): Promise<TickerHistoryPoint[]> {
  return apiFetch<TickerHistoryPoint[]>(
    `${API_BASE_URL}/api/market/tickers/${encodeURIComponent(symbol)}/history?period=${period}`
  );
}

export async function refreshMarketData(): Promise<{ status: string; count: number; refreshed_at: string }> {
  return apiFetch<{ status: string; count: number; refreshed_at: string }>(`${API_BASE_URL}/api/market/refresh`, {
    method: "POST",
  });
}

// --- AI / Co-Pilot ---

export interface AIPredictRequest {
  symbol: string;
  question: string;
  history_points?: TickerHistoryPoint[];
  news_headlines?: string[];
}

export interface AIPredictResponse {
  symbol: string;
  prediction: string;
  summary: string;
  stance: "pozitif" | "negatif" | "nötr" | string;
  sentiment: string;
  confidence: "düşük" | "orta" | "yüksek" | string;
  technical_view: string;
  catalysts: string[];
  risks: string[];
  data_quality: string;
  metrics: Record<string, number | string | null>;
  reasoning?: string | null;
  disclaimer: string;
  generated_at: string;
}

export async function predictAI(request: AIPredictRequest): Promise<AIPredictResponse> {
  return apiFetch<AIPredictResponse>(`${API_BASE_URL}/api/ai/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}
