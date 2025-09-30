import { test, expect } from '@playwright/test'

test('app démarre (smoke)', async ({ page }) => {
    await page.goto('/')                 // servie par vite preview (port 4173)
    await expect(page.locator('body')).toBeVisible()
})
