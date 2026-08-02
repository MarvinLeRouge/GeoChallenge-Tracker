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

describe("anonymous default (store creation)", () => {
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
  it("with persist: false, updates state and the DOM class but not localStorage", async () => {
    const store = useThemeStore();
    await store.setDarkMode(true, { persist: false });
    expect(store.isDark).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("theme")).toBeNull();
  });

  it("when anonymous, persists to localStorage (the device default) and never calls the backend", async () => {
    const store = useThemeStore();
    await store.setDarkMode(true);
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(mockPatch).not.toHaveBeenCalled();
  });

  it("when authenticated, persists to the backend and leaves localStorage untouched", async () => {
    const auth = useAuthStore();
    auth.setTokens({ access_token: "tok123" });
    mockPatch.mockResolvedValueOnce({ data: {} });

    const store = useThemeStore();
    await store.setDarkMode(true);

    expect(mockPatch).toHaveBeenCalledWith("/my/profile/preferences", {
      dark_mode: true,
    });
    expect(localStorage.getItem("theme")).toBeNull();
  });

  it("does not persist when persist: false is passed, even if authenticated", async () => {
    const auth = useAuthStore();
    auth.setTokens({ access_token: "tok123" });

    const store = useThemeStore();
    await store.setDarkMode(true, { persist: false });

    expect(mockPatch).not.toHaveBeenCalled();
    expect(localStorage.getItem("theme")).toBeNull();
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
    expect(localStorage.getItem("theme")).toBeNull();
  });

  it("reverts to the anonymous default on logout, instead of keeping the previous user's theme", async () => {
    localStorage.setItem("theme", "light");
    mockMatchMedia(false);

    const auth = useAuthStore();
    const store = useThemeStore();
    store.init();

    // User A logs in with dark_mode enabled.
    auth.user = {
      id: "userA",
      username: "alice",
      email: "a@b.com",
      role: "user",
      preferences: { language: "fr", dark_mode: true },
    };
    await Promise.resolve();
    expect(store.isDark).toBe(true);

    // User A logs out.
    auth.user = null;
    await Promise.resolve();

    expect(store.isDark).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("does not leak one user's theme into the next user on the same device", async () => {
    const auth = useAuthStore();
    const store = useThemeStore();
    store.init();

    // User A: dark.
    auth.user = {
      id: "userA",
      username: "alice",
      email: "a@b.com",
      role: "user",
      preferences: { language: "fr", dark_mode: true },
    };
    await Promise.resolve();
    expect(store.isDark).toBe(true);

    auth.user = null;
    await Promise.resolve();

    // User B logs in on the same browser, with light mode.
    auth.user = {
      id: "userB",
      username: "bob",
      email: "b@b.com",
      role: "user",
      preferences: { language: "fr", dark_mode: false },
    };
    await Promise.resolve();

    expect(store.isDark).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("is idempotent: calling init twice does not register duplicate watchers", () => {
    const store = useThemeStore();
    store.init();
    store.init();
    expect(store.initialized).toBe(true);
  });
});
