/** Diet Balancer design tokens.
 *  canopy/leaf/sprout: brand greens · mist: page · ink/slate: text
 *  river/wheat/beet: protein/carbs/fat — used consistently in every chart. */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        canopy: { DEFAULT: "#1F5F3F", dark: "#164730" },
        leaf: { DEFAULT: "#3E8E5E", light: "#5FAA7C" },
        sprout: { DEFAULT: "#CFE8D3", light: "#E7F3E9" },
        mist: "#F4F7F2",
        ink: "#18261D",
        slate: { DEFAULT: "#5B6B60", light: "#8A988E" },
        line: "#E2E9E1",
        river: { DEFAULT: "#2F6E8F", light: "#DCEBF2" },
        wheat: { DEFAULT: "#C9962B", light: "#F7ECD3" },
        beet: { DEFAULT: "#9A5B8C", light: "#F1E3EE" },
        alert: { DEFAULT: "#B4412F", light: "#F8E4E0" },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["Figtree", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(24, 38, 29, 0.04), 0 4px 16px -6px rgba(31, 95, 63, 0.10)",
        lift: "0 12px 32px -12px rgba(31, 95, 63, 0.28)",
      },
      keyframes: {
        "ring-in": { from: { strokeDashoffset: "var(--ring-full)" }, to: { strokeDashoffset: "var(--ring-offset)" } },
        "toast-in": { from: { opacity: 0, transform: "translateY(8px)" }, to: { opacity: 1, transform: "none" } },
        radar: { "0%": { transform: "scale(0.7)", opacity: "0.55" }, "100%": { transform: "scale(1.35)", opacity: "0" } },
        pulseDot: { "0%,100%": { opacity: 1 }, "50%": { opacity: 0.35 } },
      },
      animation: {
        "ring-in": "ring-in 900ms cubic-bezier(.2,.8,.2,1) both",
        "toast-in": "toast-in 180ms ease-out both",
        "pulse-dot": "pulseDot 1.6s ease-in-out infinite",
        radar: "radar 2.2s ease-out infinite",
      },
    },
  },
  plugins: [],
};
