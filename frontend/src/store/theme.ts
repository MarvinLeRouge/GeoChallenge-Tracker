import { defineStore } from "pinia";
import { watch } from "vue";
import api from "@/api/http";
import { useAuthStore } from "@/store/auth";

const STORAGE_KEY = "theme";

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * The device-level default: used before any auth state is known, and
 * whenever nobody is logged in. Never influenced by an authenticated
 * user's own preference, so one account's choice can't leak into another
 * account (or into the anonymous state) on a shared browser.
 */
function readAnonymousPreference(): boolean {
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
    isDark: readAnonymousPreference(),
    initialized: false,
  }),
  actions: {
    /**
     * Call once on app start. Applies the anonymous/system-derived theme
     * immediately, then tracks the authenticated user's stored preference:
     * adopted (without touching the anonymous default) while logged in,
     * and reverted back to the anonymous default on logout.
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
          } else {
            // Logged out (or no stored preference yet): fall back to the
            // anonymous default rather than keeping the last user's theme.
            this.setDarkMode(readAnonymousPreference(), { persist: false });
          }
        },
        { immediate: true },
      );
    },

    /**
     * Sets the theme, always applying it to the DOM immediately.
     *
     * - Authenticated users: persisted to the backend (their own account
     *   preference), the shared anonymous default is left untouched.
     * - Anonymous users: persisted to localStorage as the device default.
     * - `persist: false` skips both (used when adopting a value that
     *   already came from the backend, or when reverting on logout).
     */
    async setDarkMode(isDark: boolean, options: { persist?: boolean } = {}) {
      this.isDark = isDark;
      applyDarkClass(isDark);

      if (options.persist === false) return;

      const auth = useAuthStore();
      if (!auth.isAuthenticated) {
        localStorage.setItem(STORAGE_KEY, isDark ? "dark" : "light");
        return;
      }

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
