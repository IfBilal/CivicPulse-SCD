/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `npm run dev` (mode "mock") serves everything from MSW — no backend needed.
// `npm run dev:live` proxies /api to a backend you run yourself; the target is a developer-machine
// setting only and never reaches the bundle (API_BASE is always the relative "/api", ADR-0002).
const liveTarget = process.env.CIVICPULSE_API_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": { target: liveTarget, changeOrigin: false } } },
  build: {
    sourcemap: false,
    // three.js (~130 kB gz) is only reached through the lazy PulseField chunk, never the entry.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: { manualChunks: { three: ["three"], gsap: ["gsap"], react: ["react", "react-dom", "react-router-dom"] } },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    css: false,
    coverage: { provider: "v8", include: ["src/**"], reporter: ["text", "lcov"] },
  },
});
