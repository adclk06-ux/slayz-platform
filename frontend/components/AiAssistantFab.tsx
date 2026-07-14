"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { AssistantChatMessage, chatWithAssistant, ChatResponse } from "@/lib/api";

const HEADER_TITLE = "Slayz AI Analyst Assistant";
const HEADER_SUBTITLE = "Pano üzerinden analiz";

export default function AiAssistantFab() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<AssistantChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, open]);

  function handleAction(response: ChatResponse) {
    if (!response.action) return;
    const action = response.action;
    if (action.type === "focus_ticker" && action.symbol) {
      router.push(`/terminal?ticker=${encodeURIComponent(action.symbol)}`);
      setOpen(false);
    } else if (action.type === "open_terminal") {
      router.push("/terminal");
      setOpen(false);
    }
  }

  async function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    const nextMessages: AssistantChatMessage[] = [...messages, { role: "user", content: trimmed }];
    setMessages(nextMessages);
    setInput("");
    setError(null);
    setSending(true);
    try {
      const response = await chatWithAssistant(nextMessages);
      setMessages([...nextMessages, { role: "assistant", content: response.reply }]);
      handleAction(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI asistanına ulaşılamadı.");
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-[360px] max-w-[calc(100vw-2rem)] h-[480px] max-h-[calc(100vh-8rem)] flex flex-col rounded-2xl border border-slate-100 bg-white shadow-2xl shadow-slate-300/40 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-slate-900 to-indigo-950">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-white/10 border border-white/10 flex items-center justify-center shadow-inner shadow-black/10">
                <Sparkles className="w-4 h-4 text-indigo-200" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white leading-tight">{HEADER_TITLE}</p>
                <p className="text-[11px] text-indigo-200/70 leading-tight">{HEADER_SUBTITLE}</p>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="p-1.5 rounded-lg hover:bg-white/10 transition"
              aria-label="AI Asistanı Kapat"
            >
              <X className="w-4 h-4 text-slate-300" />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-white">
            {messages.length === 0 && (
              <div className="text-center text-slate-400 text-sm py-10 px-4">
                Panodaki haberler hakkında soru sorun — örneğin &ldquo;BIST100&apos;deki son gelişmeleri özetler misin?&rdquo;
              </div>
            )}
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-slate-900 text-white rounded-br-sm"
                      : "bg-slate-50 text-slate-700 border border-slate-100 rounded-bl-sm"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bg-slate-50 border border-slate-100 rounded-2xl rounded-bl-sm px-3.5 py-2.5 text-sm text-slate-400">
                  Yazıyor...
                </div>
              </div>
            )}
            {error && (
              <div className="p-3 rounded-xl bg-rose-50 text-rose-600 text-xs border border-rose-100">{error}</div>
            )}
          </div>

          <div className="p-3 border-t border-slate-100 flex items-center gap-2 bg-white">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Bir soru sorun..."
              className="flex-1 px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-900 bg-slate-50/50 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 focus:border-indigo-500/30 focus:bg-white transition"
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className="w-10 h-10 shrink-0 rounded-xl bg-gradient-to-br from-slate-900 to-indigo-950 text-white shadow-md shadow-indigo-900/20 flex items-center justify-center hover:shadow-lg hover:shadow-indigo-900/25 hover:-translate-y-0.5 transition-all disabled:opacity-40 disabled:translate-y-0 disabled:shadow-none"
              aria-label="Gönder"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((prev) => !prev)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-slate-900 text-white shadow-xl shadow-indigo-900/25 flex items-center justify-center transition-all duration-300 hover:scale-110 hover:shadow-2xl hover:shadow-indigo-900/30 active:scale-95 ring-2 ring-white ring-offset-2 ring-offset-slate-50"
        aria-label="AI Asistanı Aç"
      >
        <span className="absolute inset-0 rounded-full bg-gradient-to-tr from-indigo-600/20 to-white/10 pointer-events-none" />
        {open ? <X className="w-6 h-6 relative" /> : <Bot className="w-6 h-6 relative" />}
      </button>
    </>
  );
}
