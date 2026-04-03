import { defineConfig } from "vitest/config";
import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
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
      exclude: [
        "src/main.ts",
        "src/**/*.d.ts",
        // Pure type definitions — no executable logic
        "src/types/auth.ts",
        "src/types/challenges.ts",
        "src/types/http.ts",
        "src/types/profile.ts",
        "src/types/stats.ts",
        "src/types/index.ts",
        // Constants — no logic
        "src/constants/**",
        // Pure data config
        "src/config/cache-types.ts",
        // Static presentation — no unit-testable logic
        "src/App.vue",
        "src/pages/404.vue",
        "src/pages/_NotImplemented.vue",
        "src/pages/misc/Legal.vue",
        "src/pages/caches/MapDemo.vue",
        "src/pages/Home.vue",
        // Map-heavy pages — Leaflet/cluster/DOMPurify interactions not unit-testable
        "src/pages/Targets.vue",
        "src/components/map/MapBase.vue",
        "src/pages/caches/WithinBbox.vue",
        "src/pages/caches/WithinRadius.vue",
        // File upload page — complex multipart/fetch interactions not unit-testable
        "src/pages/caches/ImportGpx.vue",
        // Large profile form — complex validation/geocoding interactions not unit-testable
        "src/pages/profile/MyProfile.vue",
        // Global app shell — router/auth/transition orchestration not unit-testable
        "src/app/AppShell.vue",
      ],
    },
  },
});
