import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': '/src' } },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    watch: { usePolling: true, interval: 100 },
    hmr: { host: 'localhost', clientPort: 5173 },
    proxy: {
      '^/api': {
        target: 'http://backend:8000', // nom du service Docker
        changeOrigin: true,
        rewrite: p => p.replace(/^\/api/, '')
      },
      '^/tiles': {                    // DOIT rester avant un éventuel catch-all
        target: 'http://tiles:80', // conteneur nginx tiles
        changeOrigin: true,
        // pas de rewrite: on garde /tiles/... pour que tiles.conf fasse son rewrite interne
      },
  
    }
  },
  
})
