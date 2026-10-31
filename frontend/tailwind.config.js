// Every themed color is a CSS variable holding "R G B", defined for light and dark in src/index.css.
// Tailwind fills in the opacity, so classes like bg-ink-900/60 keep working in both themes.
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces: 950 is the page, 900 a card, 800 a raised or hovered surface, 700 and 600 borders.
        ink: { 950: v("ink-950"), 900: v("ink-900"), 800: v("ink-800"), 700: v("ink-700"), 600: v("ink-600") },
        // Text: a lower number is stronger text (darkest in light mode, lightest in dark mode).
        slate: { 100: v("tx-100"), 200: v("tx-200"), 300: v("tx-300"), 400: v("tx-400"), 500: v("tx-500"), 600: v("tx-600") },
        // Colored text that must stay readable on both backgrounds
        ok: v("ok"),
        warn: v("warn"),
        info: v("info"),
        vio: v("vio"),
        bad: v("bad"),
        // The main button and the active pill, with the text color that sits on them
        accent: v("accent"),
        "on-accent": v("on-accent"),
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
      boxShadow: {
        glow: "0 0 0 1px rgba(99,102,241,.4), 0 12px 30px -10px rgba(99,102,241,.35)",
        lift: "0 12px 28px -12px rgb(var(--shadow) / .4)",
      },
      keyframes: {
        sweep: { to: { transform: "rotate(360deg)" } },
        shimmer: { to: { backgroundPosition: "-200% 0" } },
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
      },
      animation: {
        sweep: "sweep 4s linear infinite",
        shimmer: "shimmer 1.6s linear infinite",
        float: "float 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
