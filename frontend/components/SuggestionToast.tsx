"use client";

import { useEffect, useState } from "react";
import { Lightbulb, X } from "lucide-react";

const SUGGESTION_TEMPLATES = [
  "BIST100 hacim analizi ister misin?",
  "Altın/Dolar paritesinde son dakika kırılımını özetleyeyim mi?",
  "Bitcoin'deki son 24 saatlik oynaklığı analiz edeyim mi?",
  "Fed faiz kararının borsaya olası etkilerini özetleyebilirim.",
  "Bugünkü emtia haberlerinde öne çıkan başlıkları görmek ister misin?",
  "Kripto para haberlerinde dikkat çeken bir trend var, incelemek ister misin?",
  "Son onaylanan haberlerin duygu durumu dağılımını çıkarabilirim.",
  "Gümüş/Ons fiyatındaki hareketliliği yorumlayabilirim.",
  "Hangi haberin ekip için paylaşılmaya değer olduğunu birlikte değerlendirelim mi?",
  "Bugün en çok işlem gören hisselerle ilgili bir özet ister misin?",
];

function pickNextSuggestion(current: string | null): string {
  if (SUGGESTION_TEMPLATES.length <= 1) return SUGGESTION_TEMPLATES[0];
  let next = current;
  while (next === current) {
    next = SUGGESTION_TEMPLATES[Math.floor(Math.random() * SUGGESTION_TEMPLATES.length)];
  }
  return next as string;
}

const ROTATION_INTERVAL_MS = 15000;

export default function SuggestionToast() {
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    setSuggestion(pickNextSuggestion(null));

    const interval = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setSuggestion((prev) => pickNextSuggestion(prev));
        setVisible(true);
      }, 250);
    }, ROTATION_INTERVAL_MS);

    return () => clearInterval(interval);
  }, []);

  if (dismissed || !suggestion) return null;

  return (
    <div
      className={`fixed bottom-6 left-6 z-40 max-w-xs transition-all duration-300 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
      }`}
    >
      <div className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-white shadow-lg shadow-slate-300/30 px-4 py-3.5">
        <div className="w-8 h-8 shrink-0 rounded-lg bg-amber-50 flex items-center justify-center">
          <Lightbulb className="w-4 h-4 text-amber-500" />
        </div>
        <p className="text-sm text-slate-600 leading-snug pt-0.5">{suggestion}</p>
        <button
          onClick={() => setDismissed(true)}
          className="shrink-0 p-1 rounded-md hover:bg-slate-50 transition"
          aria-label="Kapat"
        >
          <X className="w-3.5 h-3.5 text-slate-300" />
        </button>
      </div>
    </div>
  );
}
