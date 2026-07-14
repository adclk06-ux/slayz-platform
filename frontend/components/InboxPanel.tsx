"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ChatUser,
  InboxMessage,
  createInboxMessage,
  fetchChatUsers,
  fetchInbox,
  markAllInboxAsRead,
  markInboxAsRead,
} from "@/lib/api";
import { Inbox, MailOpen, PenLine, Send, X } from "lucide-react";

interface InboxPanelProps { isOpen: boolean; onClose: () => void; }

function formatInboxTime(iso: string): string {
  const date = new Date(iso);
  const diffMin = Math.floor((Date.now() - date.getTime()) / 60000);
  if (diffMin < 1) return "az önce";
  if (diffMin < 60) return `${diffMin} dk önce`;
  return date.toLocaleDateString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function InboxPanel({ isOpen, onClose }: InboxPanelProps) {
  const [messages, setMessages] = useState<InboxMessage[]>([]);
  const [users, setUsers] = useState<ChatUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [compose, setCompose] = useState(false);
  const [recipientId, setRecipientId] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let mounted = true;
    const refresh = () => fetchInbox().then((data) => mounted && setMessages(data)).catch(() => undefined);
    setLoading(true);
    Promise.all([fetchInbox(), fetchChatUsers()])
      .then(([inbox, roster]) => { if (mounted) { setMessages(inbox); setUsers(roster); } })
      .catch((err) => mounted && setError(err instanceof Error ? err.message : "Gelen kutusu yüklenemedi."))
      .finally(() => mounted && setLoading(false));
    const interval = setInterval(refresh, 15000);
    return () => { mounted = false; clearInterval(interval); };
  }, [isOpen]);

  async function handleMarkRead(id: string) {
    try {
      await markInboxAsRead(id);
      setMessages((prev) => prev.map((m) => m.id === id ? { ...m, is_read: true } : m));
    } catch (err) { setError(err instanceof Error ? err.message : "Mesaj güncellenemedi."); }
  }

  async function handleMarkAllRead() {
    try {
      await markAllInboxAsRead();
      setMessages((prev) => prev.map((m) => ({ ...m, is_read: true })));
    } catch (err) { setError(err instanceof Error ? err.message : "Mesajlar güncellenemedi."); }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    setSending(true); setError(null); setNotice(null);
    try {
      await createInboxMessage({ recipient_id: recipientId, title, content });
      const name = users.find((user) => user.id === recipientId)?.full_name || "Ekip arkadaşınız";
      setNotice(`${name} kişisine gönderildi.`);
      setRecipientId(""); setTitle(""); setContent(""); setCompose(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Mesaj gönderilemedi."); }
    finally { setSending(false); }
  }

  return (
    <div className={`fixed inset-y-0 left-0 z-50 w-full sm:w-[440px] bg-white border-r border-slate-200 shadow-2xl transform transition-transform duration-300 ${isOpen ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div className="flex items-center gap-2"><Inbox className="h-5 w-5 text-indigo-600" /><div><h2 className="font-bold text-slate-900">Gelen Kutusu</h2><p className="text-[11px] text-slate-400">Yalnızca size gönderilen ekip notları</p></div></div>
          <div className="flex items-center gap-1">
            <button onClick={() => { setCompose((value) => !value); setError(null); setNotice(null); }} className="rounded-lg p-2 text-indigo-600 hover:bg-indigo-50" title="Yeni mesaj"><PenLine className="h-4 w-4" /></button>
            <button onClick={handleMarkAllRead} className="rounded-lg px-2 py-2 text-[11px] font-semibold text-slate-500 hover:bg-slate-100">Tümünü oku</button>
            <button onClick={onClose} className="rounded-lg p-2 hover:bg-slate-100"><X className="h-5 w-5 text-slate-500" /></button>
          </div>
        </div>

        {(error || notice) && <div className={`mx-4 mt-3 rounded-xl p-3 text-xs ${error ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}>{error || notice}</div>}

        {compose && (
          <form onSubmit={sendMessage} className="space-y-3 border-b border-slate-100 bg-slate-50/70 p-4">
            <select required value={recipientId} onChange={(e) => setRecipientId(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-500"><option value="">Alıcı seçin</option>{users.map((user) => <option key={user.id} value={user.id}>{user.full_name}{user.is_online ? " · çevrimiçi" : ""}</option>)}</select>
            <input required maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Konu" className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-indigo-500" />
            <textarea required maxLength={5000} rows={4} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Mesajınızı yazın..." className="w-full resize-none rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-indigo-500" />
            <button disabled={sending} className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"><Send className="h-4 w-4" />{sending ? "Gönderiliyor..." : "Gönder"}</button>
          </form>
        )}

        <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50/50 p-5">
          {loading ? <div className="py-10 text-center text-sm text-slate-400">Yükleniyor...</div> : messages.length === 0 ? <div className="py-10 text-center text-sm text-slate-400">Henüz size gönderilmiş mesaj yok.</div> : messages.map((msg) => (
            <article key={msg.id} onClick={() => !msg.is_read && handleMarkRead(msg.id)} className={`cursor-pointer rounded-2xl border p-4 transition ${msg.is_read ? "border-slate-100 bg-white" : "border-indigo-100 bg-indigo-50/50"}`}>
              <div className="mb-2 flex items-start justify-between gap-3"><h3 className={`text-sm font-semibold ${msg.is_read ? "text-slate-700" : "text-slate-900"}`}>{msg.title}</h3>{!msg.is_read && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-indigo-600" />}</div>
              <p className="mb-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-600">{msg.content}</p>
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400"><span><strong className="font-medium text-slate-500">{msg.sender_name}</strong> · {formatInboxTime(msg.created_at)}</span>{!msg.is_read && <span className="inline-flex items-center gap-1 font-semibold text-indigo-600"><MailOpen className="h-3.5 w-3.5" /> Açınca okundu</span>}</div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
