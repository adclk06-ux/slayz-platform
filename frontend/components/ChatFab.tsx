"use client";

import { MessageSquare } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export default function ChatFab() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const hidden = pathname === "/chat" || pathname === "/login" || pathname === "/setup" || pathname === "/landing";
  if (hidden || loading || !user) return null;

  return (
    <button
      onClick={() => router.push("/chat")}
      aria-label="Desk Chat'i aç"
      className="group fixed bottom-6 right-24 z-50 flex h-14 items-center justify-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-600 px-4 text-white shadow-lg shadow-indigo-600/30 transition-all hover:scale-105 hover:bg-indigo-700 hover:shadow-xl active:scale-95 sm:px-5"
    >
      <MessageSquare className="h-5 w-5" />
      <span className="hidden text-sm font-semibold sm:inline">Desk Chat</span>
    </button>
  );
}
