import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Cascadia Code", "monospace"],
      },
      colors: {
        surface: "#111111",
        card: "#1a1a1a",
        border: "#2a2a2a",
        accent: "#6366f1",
        "accent-hover": "#818cf8",
        muted: "#6b7280",
        subtle: "#374151",
      },
    },
  },
  plugins: [],
};

export default config;
