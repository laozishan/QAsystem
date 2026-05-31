import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        line: "#d9e1e7",
        mist: "#f6f8f9",
        brand: "#146c5f",
        accent: "#b65f2a",
      },
    },
  },
  plugins: [],
};

export default config;

