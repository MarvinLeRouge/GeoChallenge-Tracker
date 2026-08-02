import { describe, it, expect, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const mockPatch = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { patch: mockPatch } }));

import { useThemeStore } from "@/store/theme";
import { useAuthStore } from "@/store/auth";

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
}

beforeEach(() => {
  setActivePinia(createPinia());
  localStorage.clear();
  document.documentElement.classList.remove("dark");
  mockPatch.mockReset();
  mockMatchMedia(false);
});

describe("readInitialDarkMode (store creation)", () => {
  it("defaults to system preference when nothing stored", () => {
    mockMatchMedia(true);
    const store = useThemeStore();
    expect(store.isDark).toBe(true);
  });

  it("uses light when system prefers light and nothing stored", () => {
    mockMatchMedia(false);
    const store = useThemeStore();
    expect(store.isDark).toBe(false);
  });

  it("prefers a stored 'dark' value over the system preference", () => {
    localStorage.setItem("theme", "dark");
    mockMatchMedia(false);
    const store = useThemeStore();
    expect(store.isDark).toBe(true);
  });

  it("prefers a stored 'light' value over the system preference", () => {
    localStorage.setItem("theme", "light");
    mockMatchMedia(true);
    const store = useThemeStore();
    expect(store.isDark).toBe(false);
  });
});

describe("setDarkMode", () => {
  it("updates state, the DOM class, and localStorage", async () => {
    const store = useThemeStore();
    await store.setDarkMode(true, { persist: false });
    expect(store.isDark).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("theme")).toBe("dark");

    await store.setDarkMode(false, { persist: false });
    expect(store.isDark).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("theme")).toBe("light");
  });

  it("does not call the backend when the user is not authenticated", async () => {
    const store = useThemeStore();
    await store.setDarkMode(true);
    expect(mockPatch).not.toHaveBeenCalled();
  });

  it("persists to the backend when the user is authenticated", async () => {
    const auth = useAuthStore();
    auth.setTokens({ access_token: "tok123" });
    mockPatch.mockResolvedValueOnce({ data: {} });

    const store = useThemeStore();
    await store.setDarkMode(true);

    expect(mockPatch).toHaveBeenCalledWith("/my/profile/preferences", {
      dark_mode: true,
    });
  });

  it("does not persist when persist: false is passed, even if authenticated", async () => {
    const auth = useAuthStore();
    auth.setTokens({ access_token: "tok123" });

    const store = useThemeStore();
    await store.setDarkMode(true, { persist: false });

    expect(mockPatch).not.toHaveBeenCalled();
  });

  it("keeps the local theme applied even if the backend call fails", async () => {
    const auth = useAuthStore();
    auth.setTokens({ access_token: "tok123" });
    mockPatch.mockRejectedValueOnce(new Error("network error"));

    const store = useThemeStore();
    await store.setDarkMode(true);

    expect(store.isDark).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});

describe("toggle", () => {
  it("flips the current value", async () => {
    const store = useThemeStore();
    store.isDark = false;
    await store.toggle();
    expect(store.isDark).toBe(true);
    await store.toggle();
    expect(store.isDark).toBe(false);
  });
});

describe("init", () => {
  it("applies the initial theme to the DOM", () => {
    mockMatchMedia(true);
    const store = useThemeStore();
    store.init();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("adopts the authenticated user's stored preference without re-persisting it", async () => {
    const auth = useAuthStore();
    const store = useThemeStore();
    store.init();

    auth.user = {
      id: "u1",
      username: "alice",
      email: "a@b.com",
      role: "user",
      preferences: { language: "fr", dark_mode: true },
    };
    await Promise.resolve();

    expect(store.isDark).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(mockPatch).not.toHaveBeenCalled();
  });

  it("is idempotent: calling init twice does not register duplicate watchers", () => {
    const store = useThemeStore();
    store.init();
    store.init();
    expect(store.initialized).toBe(true);
  });
});
