import { defineConfig } from "vitest/config";
import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./frontend/src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: [
      "frontend/tests/unit/*.{test,spec}.ts?(x)",
      "frontend/tests/unit/*.{test,spec}.js?(x)",
    ],
    exclude: [
      "node_modules/**",
      "frontend/dist/**",
      "frontend/tests/e2e/**",
      "**/*.e2e.*",
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      reportsDirectory: "frontend/coverage",
      include: ["frontend/src/**"],
      exclude: [
        "frontend/src/main.ts",
        "frontend/src/**/*.d.ts",
        // Pure type definitions — no executable logic
        "frontend/src/types/auth.ts",
        "frontend/src/types/challenges.ts",
        "frontend/src/types/http.ts",
        "frontend/src/types/profile.ts",
        "frontend/src/types/stats.ts",
        "frontend/src/types/index.ts",
        // Constants — no logic
        "frontend/src/constants/**",
        // Pure data config
        "frontend/src/config/cache-types.ts",
        // Static presentation — no unit-testable logic
        "frontend/src/App.vue",
        "frontend/src/pages/404.vue",
        "frontend/src/pages/_NotImplemented.vue",
        "frontend/src/pages/misc/Legal.vue",
        "frontend/src/pages/caches/MapDemo.vue",
        "frontend/src/pages/Home.vue",
        // Map-heavy pages — Leaflet/cluster/DOMPurify interactions not unit-testable
        "frontend/src/pages/Targets.vue",
        "frontend/src/components/map/MapBase.vue",
        "frontend/src/pages/caches/WithinBbox.vue",
        "frontend/src/pages/caches/WithinRadius.vue",
        // File upload page — complex multipart/fetch interactions not unit-testable
        "frontend/src/pages/caches/ImportGpx.vue",
        // Large profile form — complex validation/geocoding interactions not unit-testable
        "frontend/src/pages/profile/MyProfile.vue",
        // Global app shell — router/auth/transition orchestration not unit-testable
        "frontend/src/app/AppShell.vue",
      ],
    },
  },
});
