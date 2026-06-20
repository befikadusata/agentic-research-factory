import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          700: '#1e40af',
          900: '#1e3a8a',
        },
        cta: '#22c55e',
        status: {
          pending: { bg: "#3f3f46", text: "#d4d4d8" },
          researching: { bg: "#1e3a8a", text: "#bfdbfe" },
          awaiting_hitl: { bg: "#78350f", text: "#fde68a" },
          writing: { bg: "#4c1d95", text: "#ddd6fe" },
          complete: { bg: "#064e3b", text: "#a7f3d0" },
          failed: { bg: "#7f1d1d", text: "#fecaca" },
        },
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'sans-serif'],
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};

export default config;
