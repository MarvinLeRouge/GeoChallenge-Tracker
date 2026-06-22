import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  root: fileURLToPath(new URL("./frontend", import.meta.url)),
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./frontend/src", import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    allowedHosts: ["gc-tracker.marvinlerouge.local"],
    watch: { usePolling: true, interval: 100 },
    hmr: { host: "gc-tracker.marvinlerouge.local", clientPort: 80 },
    proxy: {
      "^/api": {
        target: "http://backend:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
      "^/tiles": {
        target: "http://tiles:80",
        changeOrigin: true,
      },
    },
  },
});
