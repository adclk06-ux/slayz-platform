"use client";

import { useEffect, useMemo, useState } from "react";
import { Article, ChatUser, createRoom, fetchChatUsers, sendRoomMessage } from "@/lib/api";
import { CheckCircle2, Search, Send, X } from "lucide-react";

interface ShareToChatModalProps {
  article: Article | null;
  onClose: () => void;
}

export default function ShareToChatModal({ article, onClose }: ShareToChatModalProps) {
  const [users, setUsers] = useState<ChatUser[]>([]);
  const [query, setQuery] = useState("");
  const [sendingTo, setSendingTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  useEffect(() => {
    if (!article) return;
    setQuery("");
    setError(null);
    setSentTo(null);
    fetchChatUsers().then(setUsers).catch((err) => setError(err instanceof Error ? err.message : "Ekip listesi yüklenemedi."));
  }, [article]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("tr-TR");
    return users.filter((user) => !needle || user.full_name.toLocaleLowerCase("tr-TR").includes(needle));
  }, [query, users]);

  if (!article) return null;

  async function share(user: ChatUser) {
    setSendingTo(user.id);
    setError(null);
    try {
      const room = await createRoom({ type: "direct", member_ids: [user.id] });
      const title = article?.ai_title || article?.raw_title;
      const summary = article?.ai_summary || article?.raw_content?.slice(0, 300) || "";
      const text = [
        `📰 ${title}`,
        `${article?.source_name} • ${new Date(article!.scraped_at).toLocaleString("tr-TR")}`,
        summary,
        article?.source_url,
      ].filter(Boolean).join("\n\n");
      await sendRoomMessage(room.id, text);
      setSentTo(user.full_name);
      setTimeout(onClose, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Haber paylaşılamadı.");
    } finally {
      setSendingTo(null);
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="w-full max-w-md overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-100 px-5 py-4">
          <div><h2 className="font-bold text-slate-900">Haberi kiminle paylaşacaksın?</h2><p className="mt-1 line-clamp-1 text-xs text-slate-500">{article.ai_title || article.raw_title}</p></div>
          <button onClick={onClose} className="rounded-lg p-2 hover:bg-slate-100"><X className="h-4 w-4" /></button>
        </div>
        {sentTo ? <div className="flex flex-col items-center gap-3 px-6 py-12 text-center"><CheckCircle2 className="h-10 w-10 text-emerald-500" /><div className="font-semibold text-slate-900">{sentTo} kişisine gönderildi</div><p className="text-xs text-slate-500">Sohbet sayfasına yönlendirilmeden paylaşım tamamlandı.</p></div> : <>
          <div className="p-4"><div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3"><Search className="h-4 w-4 text-slate-400" /><input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ekip arkadaşı ara..." className="w-full py-2.5 text-sm outline-none" /></div>{error && <div className="mt-3 rounded-xl bg-rose-50 p-3 text-xs text-rose-700">{error}</div>}</div>
          <div className="max-h-[390px] overflow-y-auto px-3 pb-4">
            {filtered.length === 0 ? <div className="py-10 text-center text-sm text-slate-400">Paylaşılabilecek aktif kullanıcı yok.</div> : filtered.map((user) => (
              <button key={user.id} disabled={Boolean(sendingTo)} onClick={() => share(user)} className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left hover:bg-slate-50 disabled:opacity-50">
                <div className="relative grid h-10 w-10 place-items-center rounded-full bg-indigo-100 font-bold text-indigo-700">{user.full_name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}<span className={`absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-white ${user.is_online ? "bg-emerald-500" : "bg-slate-300"}`} /></div>
                <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold text-slate-900">{user.full_name}</div><div className="text-[11px] text-slate-400">{user.is_online ? "Çevrimiçi" : "Çevrimdışı"}</div></div>
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600"><Send className="h-3.5 w-3.5" />{sendingTo === user.id ? "Gönderiliyor" : "Gönder"}</span>
              </button>
            ))}
          </div>
        </>}
      </div>
    </div>
  );
}
