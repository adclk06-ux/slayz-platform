/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "DM Sans", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          navy: "#1E293B",
          border: "#F3F4F6",
        },
      },
      keyframes: {
        "spin-slow": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "shimmer-sweep": {
          "0%": { transform: "translateX(-130%) skewX(-15deg)" },
          "100%": { transform: "translateX(130%) skewX(-15deg)" },
        },
        "trend-draw": {
          "0%": { strokeDashoffset: "200" },
          "100%": { strokeDashoffset: "0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-6px)" },
        },
        "pulse-glow": {
          "0%, 100%": { opacity: "0.55", transform: "scale(1)" },
          "50%": { opacity: "0.9", transform: "scale(1.08)" },
        },
        "pulse-dot": {
          "0%, 100%": { transform: "scale(1)", opacity: "1" },
          "50%": { transform: "scale(1.5)", opacity: "0.6" },
        },
      },
      animation: {
        "spin-slow": "spin-slow 6s linear infinite",
        shimmer: "shimmer 2.5s linear infinite",
        "shimmer-sweep": "shimmer-sweep 2.8s ease-in-out infinite",
        "trend-draw": "trend-draw 1.8s ease-out infinite alternate",
        float: "float 3s ease-in-out infinite",
        "pulse-glow": "pulse-glow 2.5s ease-in-out infinite",
        "pulse-dot": "pulse-dot 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
