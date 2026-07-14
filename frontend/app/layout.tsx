import type { Metadata } from "next";
import "./globals.css";
import AiAssistantFab from "@/components/AiAssistantFab";
import ChatFab from "@/components/ChatFab";
import { AuthProvider } from "@/components/AuthProvider";

export const metadata: Metadata = {
  title: "Slayz Haber Otomasyonu",
  description: "Enterprise finansal haber toplama, AI analiz ve küratörlük platformu.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body className="bg-white text-slate-900 font-sans antialiased min-h-screen">
        <AuthProvider>
          {children}
          <ChatFab />
          <AiAssistantFab />
        </AuthProvider>
      </body>
    </html>
  );
}
