/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0A0D11",
        panel: "#12161C",
        "panel-raised": "#161B22",
        hairline: "#1E242C",
        bull: "#3FBF7F",
        "bull-dim": "#1F4D38",
        bear: "#E5484D",
        "bear-dim": "#4D2326",
        signal: "#E8A33D",
        "signal-dim": "#4D3A1F",
        "text-primary": "#E6E9ED",
        "text-dim": "#6B7480",
        "text-faint": "#454B54",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        "tick": ["0.8125rem", { lineHeight: "1.2", letterSpacing: "0.01em" }],
      },
    },
  },
  plugins: [],
};
