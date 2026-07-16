"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChatUser,
  ChatMessage,
  Room,
  RoomMemberUser,
  createRoom,
  fetchChatUsers,
  fetchRoomMessages,
  fetchRooms,
  markRoomRead,
  sendRoomMessage,
} from "@/lib/api";
import { getSocket } from "@/lib/socket";
import { ArrowLeft, MessageSquare, Plus, Search, Send, Users, X } from "lucide-react";
import { useRouter } from "next/navigation";

interface ChatSidebarProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  showBackButton?: boolean;
}

function decodeMyUserId(): string | null {
  if (typeof window === "undefined") return null;
  const token = window.localStorage.getItem("slayz_token");
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.sub || null;
  } catch {
    return null;
  }
}

type AvatarUser = { full_name: string | null; avatar_url: string | null } | null;

function Avatar({ user, size = 40 }: { user: AvatarUser; size?: number }) {
  const initials = (user?.full_name || "Ekip")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  if (user?.avatar_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={user.avatar_url}
        alt={user.full_name || "Avatar"}
        width={size}
        height={size}
        className="rounded-full border border-slate-200 bg-slate-100 object-cover"
      />
    );
  }
  return (
    <div
      className="rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center"
      style={{ width: size, height: size, fontSize: size * 0.36 }}
    >
      {initials}
    </div>
  );
}

export default function ChatSidebar({ open, onOpenChange, showBackButton }: ChatSidebarProps) {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(open ?? false);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [roomsError, setRoomsError] = useState<string | null>(null);
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [connected, setConnected] = useState(false);
  const [typingUsers, setTypingUsers] = useState<Record<string, boolean>>({});
  const [newChatOpen, setNewChatOpen] = useState(false);
  const [chatUsers, setChatUsers] = useState<ChatUser[]>([]);
  const [userSearch, setUserSearch] = useState("");
  const [creatingRoomFor, setCreatingRoomFor] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const myIdRef = useRef<string | null>(null);
  const activeRoomIdRef = useRef<string | null>(null);
  const socketRef = useRef<ReturnType<typeof getSocket> | null>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.debug("[chat] ChatSidebar mount");
      return () => console.debug("[chat] ChatSidebar unmount", { reason: "component_unmount" });
    }
  }, []);

  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.debug("[chat] open prop changed", { open });
    }
    if (open !== undefined) setIsOpen(open);
  }, [open]);

  // Load the authenticated user's rooms.
  useEffect(() => {
    myIdRef.current = decodeMyUserId();
    let mounted = true;
    setRoomsLoading(true);
    setRoomsError(null);
    fetchRooms()
      .then((data) => {
        if (!mounted) return;
        setRooms(data);
        setRoomsLoading(false);
        // Default to the first group room or the first room if none selected.
        setActiveRoomId((prev) => {
          if (prev) return prev;
          const group = data.find((r) => r.type === "group");
          return group ? group.id : data[0]?.id || null;
        });
      })
      .catch((err) => {
        if (!mounted) return;
        setRoomsError(err instanceof Error ? err.message : "Odalar yüklenemedi.");
        setRoomsLoading(false);
      });
    const interval = setInterval(() => {
      fetchRooms()
        .then((data) => mounted && setRooms(data))
        .catch(() => undefined);
    }, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // Load message history when the selected room changes.
  useEffect(() => {
    activeRoomIdRef.current = activeRoomId;
    setTypingUsers({});
    if (!activeRoomId) {
      setMessages([]);
      return;
    }
    setMessagesLoading(true);
    fetchRoomMessages(activeRoomId, { limit: 30 })
      .then((res) => {
        setMessages(res.messages);
        const latest = res.messages.at(-1);
        if (latest) {
          markRoomRead(activeRoomId, latest.id).catch(() => undefined);
          setRooms((prev) => prev.map((room) => room.id === activeRoomId ? { ...room, unread_count: 0 } : room));
        }
      })
      .catch(() => setMessages([]))
      .finally(() => setMessagesLoading(false));

    const socket = socketRef.current;
    if (socket) {
      socket.emit("join_room", { room_id: activeRoomId });
    }
    return undefined;
  }, [activeRoomId]);

  // Reliable fallback for sleeping/reconnecting hosts. Socket.IO remains the
  // instant path; this lightweight poll guarantees messages appear without F5.
  useEffect(() => {
    if (!activeRoomId) return;
    let cancelled = false;
    const sync = async () => {
      try {
        const res = await fetchRoomMessages(activeRoomId, { limit: 50 });
        if (cancelled) return;
        setMessages((prev) => {
          const byId = new Map(prev.map((item) => [item.id, item]));
          res.messages.forEach((item) => byId.set(item.id, item));
          return Array.from(byId.values()).sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
        });
      } catch {}
    };
    const timer = window.setInterval(sync, 2500);
    const onVisible = () => { if (document.visibilityState === "visible") void sync(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => { cancelled = true; window.clearInterval(timer); document.removeEventListener("visibilitychange", onVisible); };
  }, [activeRoomId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Persistent Socket.IO connection for real-time messaging.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const token = window.localStorage.getItem("slayz_token");
    if (!token) return;

    const socket = getSocket(token);
    socketRef.current = socket;

    socket.on("connect", () => {
      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.debug("[chat] socket connect", { id: socket.id });
      }
      setConnected(true);
      const roomId = activeRoomIdRef.current;
      if (roomId) socket.emit("join_room", { room_id: roomId });
    });
    socket.on("disconnect", (reason) => {
      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.debug("[chat] socket disconnect", { reason: "socket_disconnect", detail: reason });
      }
      // A dropped socket must never close the chat screen; we only flip the
      // "Canlı" badge and let socket.io reconnect in the background.
      setConnected(false);
    });
    socket.on("connect_error", (err) => {
      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.debug("[chat] socket connect_error", { error: String(err) });
      }
      setConnected(false);
    });

    socket.on("new_message", (msg: ChatMessage) => {
      const isActive = msg.room_id === activeRoomIdRef.current;
      if (isActive) {
        setMessages((prev) => prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]);
        if (msg.sender.id !== myIdRef.current) markRoomRead(msg.room_id, msg.id).catch(() => undefined);
      }
      setRooms((prev) => {
        const next = prev.map((room) => room.id === msg.room_id ? {
          ...room,
          last_message: {
            id: msg.id,
            content: msg.content,
            created_at: msg.created_at,
            sender: { ...msg.sender, is_online: true },
          },
          unread_count: isActive || msg.sender.id === myIdRef.current ? 0 : room.unread_count + 1,
          updated_at: msg.created_at,
        } : room);
        return [...next].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
      });
    });

    socket.on("presence", (data: { user_id: string; is_online: boolean; status?: string }) => {
      setRooms((prev) => prev.map((room) => ({
        ...room,
        members: room.members.map((member) => member.id === data.user_id ? {
          ...member,
          is_online: data.is_online,
          status: data.status || member.status,
        } : member),
      })));
      setChatUsers((prev) => prev.map((member) => member.id === data.user_id ? { ...member, is_online: data.is_online, status: data.status || member.status } : member));
    });

    socket.on(
      "typing",
      (data: { room_id: string; user_id: string; is_typing: boolean }) => {
        if (data.room_id !== activeRoomIdRef.current) return;
        setTypingUsers((prev) => ({ ...prev, [data.user_id]: data.is_typing }));
      }
    );

    socket.on(
      "read_receipt",
      (data: { room_id: string; user_id: string; message_id: string }) => {
        setRooms((prev) =>
          prev.map((r) =>
            r.id === data.room_id
              ? { ...r, unread_count: Math.max(0, r.unread_count - 1) }
              : r
          )
        );
      }
    );

    return () => {
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
      socket.off("connect");
      socket.off("disconnect");
      socket.off("connect_error");
      socket.off("new_message");
      socket.off("presence");
      socket.off("typing");
      socket.off("read_receipt");
    };
  }, []);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || !activeRoomId || sending) return;
    setSending(true);
    try {
      const socket = socketRef.current;
      if (socket?.connected) {
        await new Promise<void>((resolve, reject) => {
          socket.timeout(8000).emit("send_message", { room_id: activeRoomId, content: text }, (err: Error | null, response?: { ok?: boolean; message?: string }) => {
            if (err || response?.ok === false) reject(new Error(response?.message || "Mesaj gönderilemedi."));
            else resolve();
          });
        });
        setInput("");
      } else {
        const message = await sendRoomMessage(activeRoomId, text);
        setMessages((prev) => [...prev, message]);
        setInput("");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Mesaj gönderilemedi.";
      window.alert(message);
    } finally {
      setSending(false);
    }
  };

  const handleInputChange = (value: string) => {
    setInput(value);
    const socket = socketRef.current;
    if (!socket?.connected || !activeRoomId) return;
    socket.emit("typing", { room_id: activeRoomId, is_typing: true });
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(() => {
      socket.emit("typing", { room_id: activeRoomId, is_typing: false });
    }, 1500);
  };

  const activeRoom = useMemo(
    () => rooms.find((r) => r.id === activeRoomId) || null,
    [rooms, activeRoomId]
  );
  const activeOther = useMemo(() => {
    if (!activeRoom || activeRoom.type !== "direct") return null;
    return activeRoom.members.find((m) => m.id !== myIdRef.current) || activeRoom.members[0] || null;
  }, [activeRoom]);
  const activeDisplayName = activeRoom?.name || activeOther?.full_name || "Oda";

  const myId = myIdRef.current;

  async function openNewChat() {
    setNewChatOpen(true);
    setUserSearch("");
    try {
      setChatUsers(await fetchChatUsers());
    } catch (err) {
      setRoomsError(err instanceof Error ? err.message : "Kullanıcılar yüklenemedi.");
    }
  }

  async function startDirectChat(target: ChatUser) {
    setCreatingRoomFor(target.id);
    try {
      const room = await createRoom({ type: "direct", member_ids: [target.id] });
      setRooms((prev) => [room, ...prev.filter((item) => item.id !== room.id)]);
      setActiveRoomId(room.id);
      setNewChatOpen(false);
    } catch (err) {
      setRoomsError(err instanceof Error ? err.message : "Sohbet açılamadı.");
    } finally {
      setCreatingRoomFor(null);
    }
  }

  const filteredChatUsers = chatUsers.filter((member) => {
    const needle = userSearch.trim().toLocaleLowerCase("tr-TR");
    return !needle || member.full_name.toLocaleLowerCase("tr-TR").includes(needle);
  });

  return (
    <div
      className={
        "relative h-full w-full bg-white border-l border-slate-200 shadow-2xl transform transition-transform duration-300 " +
        (isOpen ? "translate-x-0" : "translate-x-full")
      }
    >
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            {showBackButton && (
              <button
                onClick={() => router.push("/")}
                className="flex items-center gap-1.5 mr-2 px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition"
                title="Ana terminale dön"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Ana Sayfaya Dön
              </button>
            )}
            <MessageSquare className="w-5 h-5 text-indigo-600" />
            <h2 className="font-bold text-slate-900 text-sm">Desk Chat</h2>
            <span
              className={
                "text-[10px] font-medium px-2 py-0.5 rounded-full " +
                (connected ? "text-emerald-600 bg-emerald-50" : "text-amber-600 bg-amber-50")
              }
            >
              {connected ? "Canlı" : "Bağlanıyor..."}
            </span>
          </div>
          <button
            onClick={() => {
              if (showBackButton) {
                router.push("/");
                return;
              }
              setIsOpen(false);
              onOpenChange?.(false);
            }}
            className="p-1.5 rounded-lg hover:bg-slate-100 transition"
          >
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* Left: room list */}
          <div className="w-[180px] sm:w-[200px] border-r border-slate-100 overflow-y-auto bg-slate-50/60">
            <div className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50/95 p-2 backdrop-blur">
              <button onClick={openNewChat} className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-2 py-2 text-xs font-semibold text-white hover:bg-indigo-700">
                <Plus className="h-3.5 w-3.5" /> Yeni Sohbet
              </button>
            </div>
            {roomsLoading && (
              <div className="px-3 py-4 text-xs text-slate-400">Odalar yükleniyor...</div>
            )}
            {roomsError && !roomsLoading && (
              <div className="px-3 py-4 text-xs text-rose-600">{roomsError}</div>
            )}
            {!roomsLoading && rooms.length === 0 && (
              <div className="px-3 py-4 text-xs text-slate-400">Henüz oda bulunmuyor.</div>
            )}

            {rooms.map((room) => {
              const isDirect = room.type === "direct";
              const other = isDirect
                ? room.members.find((m) => m.id !== myIdRef.current) || room.members[0]
                : null;
              const displayName = room.name || other?.full_name || "Oda";
              const isActive = activeRoomId === room.id;
              return (
                <button
                  key={room.id}
                  onClick={() => setActiveRoomId(room.id)}
                  className={
                    "w-full flex items-center gap-2 px-3 py-3 text-left transition hover:bg-white " +
                    (isActive ? "bg-white border-l-2 border-indigo-600" : "")
                  }
                >
                  <div className="relative shrink-0">
                    {isDirect ? (
                      <Avatar user={other || null} size={36} />
                    ) : (
                      <div className="w-9 h-9 rounded-full bg-indigo-600 text-white flex items-center justify-center shrink-0">
                        <Users className="w-4 h-4" />
                      </div>
                    )}
                    {isDirect && other && (
                      <span
                        className={
                          "absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-white " +
                          (other.is_online ? "bg-emerald-500" : "bg-slate-300")
                        }
                      />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-bold text-slate-900 truncate">{displayName}</div>
                      {room.unread_count > 0 && (
                        <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1.5 rounded-full bg-rose-500 text-white text-[10px] font-bold">
                          {room.unread_count > 99 ? "99+" : room.unread_count}
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-slate-400 truncate">
                      {room.last_message?.content || "Henüz mesaj yok"}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Right: active conversation */}
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-100 bg-white">
              {activeRoom?.type === "group" ? (
                <>
                  <div className="w-7 h-7 rounded-full bg-indigo-600 text-white flex items-center justify-center">
                    <Users className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900">{activeDisplayName}</div>
                    <div className="text-[10px] text-slate-400">Herkese açık masa sohbeti</div>
                  </div>
                </>
              ) : (
                <>
                  <Avatar user={activeOther} size={28} />
                  <div>
                    <div className="text-xs font-bold text-slate-900">{activeDisplayName}</div>
                    <div className="text-[10px] text-slate-400">
                      {activeOther?.is_online ? "Çevrimiçi" : activeOther?.status || "Çevrimdışı"}
                    </div>
                  </div>
                </>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/50">
              {messagesLoading && (
                <div className="text-center text-xs text-slate-400 py-10">Mesajlar yükleniyor...</div>
              )}
              {!messagesLoading && messages.length === 0 && (
                <div className="text-center text-xs text-slate-400 py-10">
                  Henüz mesaj yok. İlk mesajı siz gönderin.
                </div>
              )}
              {messages.map((msg) => {
                const isMine = msg.sender.id === myId;
                return (
                  <div
                    key={msg.id}
                    className={"flex " + (isMine ? "justify-end" : "justify-start")}
                  >
                    <div
                      className={
                        "max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm shadow-sm " +
                        (isMine
                          ? "bg-indigo-600 text-white rounded-br-md"
                          : "bg-white border border-slate-100 text-slate-700 rounded-bl-md")
                      }
                    >
                      {!isMine && (
                        <div className="text-[10px] font-semibold opacity-70 mb-0.5">
                          {msg.sender.full_name}
                        </div>
                      )}
                      <div className="whitespace-pre-wrap break-words">{msg.content || ""}</div>
                      {msg.created_at && (
                        <div
                          className={
                            "text-[9px] mt-1 " + (isMine ? "text-indigo-200" : "text-slate-400")
                          }
                        >
                          {new Date(msg.created_at).toLocaleTimeString("tr-TR", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
              <div ref={bottomRef}></div>
            </div>

            {Object.entries(typingUsers).some(([uid, typing]) => typing && uid !== myId) && (
              <div className="px-4 py-1.5 text-[11px] text-slate-400 bg-white border-t border-slate-50">
                {(() => {
                  const names = Object.entries(typingUsers)
                    .filter(([uid, typing]) => typing && uid !== myId)
                    .map(([uid]) => {
                      const member = activeRoom?.members.find((m) => m.id === uid);
                      return member?.full_name || "Birisi";
                    });
                  if (names.length === 1) return `${names[0]} yazıyor...`;
                  return `${names.join(", ")} yazıyor...`;
                })()}
              </div>
            )}

            <div className="p-3 border-t border-slate-100 bg-white">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => handleInputChange(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder={
                    activeRoom?.type === "group"
                      ? `${activeDisplayName}'na mesaj yazın...`
                      : `${activeDisplayName} kişisine yazın...`
                  }
                  aria-label="Mesaj yazın"
                  className="flex-1 px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
                <button
                  onClick={sendMessage}
                  disabled={!input.trim() || sending}
                  aria-label="Gönder"
                  className="p-2.5 rounded-xl bg-indigo-600 text-white disabled:opacity-50 hover:bg-indigo-700 transition"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {newChatOpen && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-slate-950/35 p-4 backdrop-blur-sm">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div><h3 className="text-sm font-bold text-slate-900">Ekip arkadaşını seç</h3><p className="text-[11px] text-slate-500">Tüm aktif @slayz.com kullanıcıları</p></div>
              <button onClick={() => setNewChatOpen(false)} className="rounded-lg p-1.5 hover:bg-slate-100"><X className="h-4 w-4" /></button>
            </div>
            <div className="p-3">
              <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3"><Search className="h-4 w-4 text-slate-400" /><input autoFocus value={userSearch} onChange={(e) => setUserSearch(e.target.value)} placeholder="İsim ara..." className="w-full py-2.5 text-sm outline-none" /></div>
            </div>
            <div className="max-h-[360px] overflow-y-auto px-2 pb-3">
              {filteredChatUsers.length === 0 ? <div className="p-8 text-center text-xs text-slate-400">Aktif ekip arkadaşı bulunamadı.</div> : filteredChatUsers.map((member) => (
                <button key={member.id} disabled={creatingRoomFor === member.id} onClick={() => startDirectChat(member)} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-slate-50 disabled:opacity-50">
                  <div className="relative"><Avatar user={{ full_name: member.full_name, avatar_url: member.avatar_url }} size={38} /><span className={`absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-white ${member.is_online ? "bg-emerald-500" : "bg-slate-300"}`} /></div>
                  <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold text-slate-900">{member.full_name}</div><div className="text-[11px] text-slate-400">{member.is_online ? "Çevrimiçi" : "Çevrimdışı"}</div></div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
