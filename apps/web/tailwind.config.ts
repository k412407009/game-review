import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          900: "#0B0D12",
          800: "#14171F",
          700: "#1C2028",
          600: "#262B34",
          500: "#3D4452",
          400: "#6B7280",
          300: "#9CA3AF",
          200: "#D1D5DB",
          100: "#F3F4F6",
        },
        accent: {
          500: "#6366F1",
          400: "#818CF8",
          300: "#A5B4FC",
        },
        success: {
          500: "#22C55E",
          100: "#D1FAE5",
        },
        warning: {
          500: "#EAB308",
          100: "#FEF3C7",
        },
        danger: {
          500: "#EF4444",
          100: "#FEE2E2",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system", "BlinkMacSystemFont", "Inter", "PingFang SC",
          "Segoe UI", "Roboto", "sans-serif",
        ],
        mono: ["SF Mono", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
