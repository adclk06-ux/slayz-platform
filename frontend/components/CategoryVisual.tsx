"use client";

import { Bitcoin, Coins } from "lucide-react";
import { NewsCategory } from "@/lib/api";

interface CategoryVisualProps {
  category: NewsCategory;
  sentiment?: string | null;
  size?: number;
}

function BitcoinVisual({ size }: { size: number }) {
  const iconSize = Math.round(size * 0.45);
  return (
    <div
      className="relative flex items-center justify-center rounded-xl bg-amber-50 border border-amber-100 shadow-sm shadow-amber-200/30 perspective-500"
      style={{ width: size, height: size }}
    >
      <div className="absolute inset-0 rounded-xl bg-amber-400/5 animate-pulse-glow" />
      <div className="relative preserve-3d flex items-center justify-center">
        <span
          className="text-3d-bitcoin font-black leading-none select-none"
          style={{ fontSize: iconSize }}
        >
          ₿
        </span>
      </div>
      <Bitcoin
        className="absolute bottom-1 right-1 text-amber-500/60 drop-shadow-sm"
        style={{ width: iconSize * 0.35, height: iconSize * 0.35 }}
        strokeWidth={2}
      />
    </div>
  );
}

function TrendLineVisual({ size, sentiment }: { size: number; sentiment?: string | null }) {
  const bullish = sentiment !== "bearish";
  const color = bullish ? "#16A34A" : "#DC2626";
  const bgTint = bullish ? "rgba(22,163,74,0.08)" : "rgba(220,38,38,0.08)";
  const path = bullish
    ? "M2 34 C 12 32, 18 20, 26 22 S 40 8, 47 10 S 57 3, 62 3"
    : "M2 6 C 12 8, 18 20, 26 18 S 40 32, 47 30 S 57 37, 62 37";

  return (
    <div
      className="relative flex items-center justify-center rounded-2xl overflow-hidden"
      style={{ width: size, height: size, background: bgTint }}
    >
      <svg viewBox="0 0 64 40" width={size * 0.82} height={size * 0.82 * 0.625}>
        <defs>
          <linearGradient id={`trendFill-${bullish ? "up" : "down"}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
          <filter id={`glow-${bullish ? "up" : "down"}`} x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="1.4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path
          d={`${path} L62 40 L2 40 Z`}
          fill={`url(#trendFill-${bullish ? "up" : "down"})`}
          stroke="none"
        />
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth="2.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter={`url(#glow-${bullish ? "up" : "down"})`}
          strokeDasharray="120"
          className="animate-trend-draw"
        />
        <circle
          cx="62"
          cy={bullish ? 3 : 37}
          r="3.5"
          fill={color}
          className="animate-pulse-dot"
          style={{ transformOrigin: `62px ${bullish ? 3 : 37}px` }}
        />
      </svg>
    </div>
  );
}

function GoldVisual({ size }: { size: number }) {
  const barHeight = size * 0.64;
  return (
    <div
      className="relative flex items-center justify-center rounded-xl overflow-hidden shadow-md"
      style={{ width: size, height: barHeight }}
    >
      <div
        className="absolute inset-0"
        style={{
          background: "linear-gradient(135deg, #FCEABB 0%, #E8C766 30%, #D4AF37 55%, #B8860B 85%, #8B6B0F 100%)",
        }}
      />
      <div className="absolute inset-0 border border-[#8B6B0F]/30 rounded-xl" />
      <div
        className="absolute inset-y-0 w-1/3 animate-shimmer-sweep"
        style={{ background: "linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.65) 50%, transparent 100%)" }}
      />
      <Coins
        className="relative text-[#5C4300] drop-shadow-sm"
        style={{ width: size * 0.36, height: size * 0.36 }}
        strokeWidth={2.25}
      />
    </div>
  );
}

export default function CategoryVisual({ category, sentiment, size = 48 }: CategoryVisualProps) {
  switch (category) {
    case "crypto":
      return <BitcoinVisual size={size} />;
    case "stocks":
      return <TrendLineVisual size={size} sentiment={sentiment} />;
    case "commodities":
      return <GoldVisual size={size} />;
    default:
      return null;
  }
}
