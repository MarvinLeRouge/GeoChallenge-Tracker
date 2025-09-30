// playwright.config.ts
import { defineConfig } from '@playwright/test'
import dotenv from 'dotenv'
import path from 'path'

// Charger les variables d'environnement depuis le niveau parent
console.log('🔍 Chargement .env.test depuis playwright.config.ts...')
const envPath = path.resolve(process.cwd(), '../.env.test')
console.log('📁 Chemin .env.test:', envPath)

const result = dotenv.config({ path: envPath })
if (result.error) {
    console.error('❌ Erreur chargement .env.test:', result.error.message)
} else {
    console.log('✅ Variables chargées depuis playwright.config.ts:', Object.keys(result.parsed || {}))
}

export default defineConfig({
    testDir: 'tests/e2e',
    use: {
        baseURL: 'http://localhost:4173',
        headless: true,
        trace: 'retain-on-failure',
    },
    webServer: {
        command: 'npm run preview:test -- --port 4173',
        url: 'http://localhost:4173',
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
    },
    projects: [
        { name: 'firefox', use: { browserName: 'firefox' } },
    ],
})
