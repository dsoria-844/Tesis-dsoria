import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Pin the time zone so date-formatting tests are deterministic on any machine / CI.
process.env.TZ = "America/Argentina/Buenos_Aires";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
  preview: { port: 4173, proxy: { "/api": "http://localhost:8000" } },
});
