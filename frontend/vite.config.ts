import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {  // si tu utilises ce fichier comme config Vitest (ok avec Vitest 3)
    environment: 'jsdom',
    globals: true,
    coverage: {
      provider: 'v8',
      include: ['src/utils/**'],
      exclude: [
        '**/*.d.ts',
        'node_modules/**',
        'dist/**',
      ],
      reportsDirectory: 'coverage',
      reporter: ['text', 'html']
    }
  },
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
