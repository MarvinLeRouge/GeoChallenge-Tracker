import { defineConfig } from "vitest/config";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: [
      "tests/unit/*.{test,spec}.ts?(x)",
      "tests/unit/*.{test,spec}.js?(x)",
    ],
    exclude: ["node_modules/**", "dist/**", "tests/e2e/**", "**/*.e2e.*"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      reportsDirectory: "./coverage",
      include: ["src/**"],
      exclude: ["src/main.ts", "src/**/*.d.ts"],
    },
  },
});
