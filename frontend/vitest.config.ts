// vitest.config.ts
import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
    resolve: {
        alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    test: {
        environment: 'jsdom',
        globals: true,
        include: [
            'tests/unit/*.{test,spec}.ts?(x)',   // ← .ts et .tsx
            'tests/unit/*.{test,spec}.js?(x)',   // ← si tu as des .js/.jsx
        ],
        exclude: ['node_modules/**', 'dist/**', 'tests/e2e/**', '**/*.e2e.*'],
        coverage: { /* ... */ },
    }
})
