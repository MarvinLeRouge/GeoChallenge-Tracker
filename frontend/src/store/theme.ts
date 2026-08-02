import { defineStore } from "pinia";
import { watch } from "vue";
import api from "@/api/http";
import { useAuthStore } from "@/store/auth";

const STORAGE_KEY = "theme";

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function readInitialDarkMode(): boolean {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "dark") return true;
  if (stored === "light") return false;
  return systemPrefersDark();
}

function applyDarkClass(isDark: boolean) {
  document.documentElement.classList.toggle("dark", isDark);
}

export const useThemeStore = defineStore("theme", {
  state: () => ({
    isDark: readInitialDarkMode(),
    initialized: false,
  }),
  actions: {
    /**
     * Call once on app start. Applies the local/system-derived theme
     * immediately, then adopts the authenticated user's stored preference
     * (once their profile loads) as the source of truth going forward.
     */
    init() {
      applyDarkClass(this.isDark);
      if (this.initialized) return;
      this.initialized = true;

      const auth = useAuthStore();
      watch(
        () => auth.user?.preferences?.dark_mode,
        (darkMode) => {
          if (darkMode !== undefined && darkMode !== null) {
            this.setDarkMode(darkMode, { persist: false });
          }
        },
        { immediate: true },
      );
    },

    /**
     * Sets the theme, always applying it locally (DOM class + localStorage).
     * Persists to the backend for authenticated users unless `persist: false`
     * (used when adopting a value that already came from the backend).
     */
    async setDarkMode(isDark: boolean, options: { persist?: boolean } = {}) {
      this.isDark = isDark;
      applyDarkClass(isDark);
      localStorage.setItem(STORAGE_KEY, isDark ? "dark" : "light");

      if (options.persist === false) return;

      const auth = useAuthStore();
      if (!auth.isAuthenticated) return;

      try {
        await api.patch("/my/profile/preferences", { dark_mode: isDark });
      } catch {
        // Best-effort: the local/DOM theme is already applied regardless of
        // whether the backend write succeeds.
      }
    },

    toggle() {
      this.setDarkMode(!this.isDark);
    },
  },
});
