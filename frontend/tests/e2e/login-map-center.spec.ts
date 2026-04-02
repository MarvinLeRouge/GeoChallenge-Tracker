import { test, expect } from "@playwright/test";

test("login → homepage → recherche par rayon", async ({ page }) => {
  const username = process.env.ADMIN_USERNAME!;
  const password = process.env.ADMIN_PASSWORD!;

  console.log(username, password);

  // STUB 1: Login (pour authentification)
  await page.route("**/auth/login", (route) => {
    console.log("🔐 Stub login appelé");
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: "tok123", refresh_token: "ref456" }),
    });
  });

  // STUB 2: Profil utilisateur (pour afficher username)
  await page.route("**/my/profile", (route) => {
    console.log("👤 Stub profile appelé");
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        _id: "689ee343223844287350eed9",
        email: "admin@geochallenge.app",
        username: "MarvinLeRougeFamily",
        role: "admin",
      }),
    });
  });

  // STUB 3: Localisation (pour centrer la carte)
  await page.route("**/my/profile/location", (route) => {
    console.log("📍 Stub location appelé");
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        lat: 43.1104666667,
        lon: 5.9426166667,
        coords: "N43 06.628 E5 56.557",
        updated_at: "2025-08-25T13:45:36.833000",
      }),
    });
  });

  // Stubber les tuiles OpenStreetMap
  await page.route("**/tile.openstreetmap.org/**", (route) => {
    console.log("🗺️ Stub tuile:", route.request().url());
    // Retourner une tuile transparente 1x1 pixel
    const transparentTile = Buffer.from([
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
      0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
      0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
      0x0d, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
      0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00, 0x00, 0x00, 0x00, 0x49,
      0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
    ]);

    return route.fulfill({
      status: 200,
      contentType: "image/png",
      body: transparentTile,
    });
  });

  // Lance l'app (vite preview via config)
  await page.goto("/");

  // Va au login (adapte si ton app y arrive déjà)
  await page.click('a[href="/login"]');

  // Remplit et submit (adapte les sélecteurs si besoin)
  await page.fill('input[name="identifier"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');

  // Attends la navigation post-login
  await page.waitForURL("/");

  // 1) username visible
  const usernameText = await page.getByTestId("username").textContent();
  console.log("🏷️ Username textContent:", `"${usernameText}"`);
  console.log("item", page.getByTestId("username"));
  await expect(page.getByTestId("username")).toHaveText("MarvinLeRougeFamily");

  // 2) carte visible avec contrôles
  await page.goto("/caches/within-radius");
  await expect(page.locator(".leaflet-container")).toBeVisible();
  await expect(
    page.locator('button[aria-label="Choisir sur la carte"]'),
  ).toBeVisible();
  await expect(page.getByTestId("current-center")).toHaveText(
    "Centre : N43 6.628 E5 56.557",
  );
});
