import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18212f",
        paper: "#f7f6f2",
        line: "#ddd8cc",
        mint: "#dff5e1",
        coral: "#ff7d64",
      },
    },
  },
  plugins: [],
};

export default config;
