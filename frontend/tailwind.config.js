/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#12141A",
          900: "#191C24",
          800: "#23272F",
          700: "#2E333D",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        panel: "0 20px 45px -30px rgba(0, 0, 0, 0.9)",
        glow: "0 0 0 1px rgba(34, 211, 238, 0.18), 0 18px 40px -24px rgba(34, 211, 238, 0.35)",
      },
      backgroundImage: {
        grid: "linear-gradient(rgba(148, 163, 184, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(148, 163, 184, 0.05) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};
