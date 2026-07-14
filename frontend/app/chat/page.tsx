"use client";

import { useEffect } from "react";
import ChatSidebar from "@/components/ChatSidebar";

export default function ChatPage() {
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.debug("[chat] ChatPage mount");
      return () => console.debug("[chat] ChatPage unmount", { reason: "component_unmount" });
    }
  }, []);

  return (
    <div className="h-screen w-screen overflow-hidden bg-slate-50">
      <ChatSidebar open={true} onOpenChange={() => {}} showBackButton={true} />
    </div>
  );
}
