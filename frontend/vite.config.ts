/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // Listens on every interface inside the container; Compose publishes it only on 127.0.0.1 (DS-10). The default
    // allowedHosts accepts localhost and IP addresses.
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Fallback when file events do not reach the container (DS-17): VITE_USE_POLLING=true in .env.
    watch: { usePolling: process.env.VITE_USE_POLLING === "true" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
