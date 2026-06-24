import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0d1324",
        muted: "#475467",
        paper: "#fffdf7",
        surface: "#ffffff",
        line: "#eee7d4",
        soft: "#fff5d6",
        gold: "#f7b801",
        "gold-strong": "#ffc400",
        mint: "#dcfce7",
        coral: "#f7b801",
      },
      boxShadow: {
        product: "0 22px 70px rgba(15, 23, 42, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
