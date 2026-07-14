import { Suspense } from "react";
import TerminalClient from "./TerminalClient";

export default function TerminalPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-400 text-sm">
          Piyasa terminali yükleniyor...
        </div>
      }
    >
      <TerminalClient />
    </Suspense>
  );
}
