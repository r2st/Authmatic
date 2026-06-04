import { defineConfig } from "vitest/config";
import { resolve } from "path";

// Test config for the web package (ticket 0010). Node environment — the
// current suites cover lib + API-route handlers, which run server-side.
// Add jsdom + @testing-library when component tests are introduced.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/__tests__/**/*.test.ts"],
    globals: false,
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
});
