<template>
  <div
    class="min-h-screen flex flex-col bg-white text-gray-900 dark:bg-gray-900 dark:text-gray-100"
  >
    <!-- Header minimal -->
    <header
      class="flex items-center justify-between px-3 py-2 border-b dark:border-gray-800"
    >
      <RouterLink
        to="/"
        class="flex items-center gap-2 -m-2 px-3 py-2 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:focus-visible:outline-gray-600"
        aria-label="Accueil"
      >
        <img :src="logoUrl" alt="GeoChallenge Tracker" class="h-11 w-auto" />
        <span class="text-lg font-semibold">GC Tracker</span>
      </RouterLink>
      <div aria-hidden="true" class="w-6 h-6" />
    </header>

    <!-- Contenu -->
    <main :class="[mainPadding, fabBottomPad]" class="flex-1 min-h-0 relative">
      <RouterView />
    </main>

    <!-- FAB (menu trigger) -->
    <button
      class="fixed bottom-[max(1rem,env(safe-area-inset-bottom))] right-[max(1rem,env(safe-area-inset-right))] z-50 h-14 w-14 rounded-full shadow-lg border border-gray-200 bg-white flex items-center justify-center active:scale-95 transition dark:border-gray-700 dark:bg-gray-800"
      aria-label="Ouvrir le menu"
      @click="openMenu()"
    >
      <Bars3Icon class="w-7 h-7" />
      <span class="sr-only">Menu</span>
    </button>

    <!-- Drawer plein écran (custom, accessible) -->
    <div
      v-if="menuOpen"
      class="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      @keydown.esc="closeMenu"
    >
      <!-- Overlay -->
      <div class="absolute inset-0 bg-black/40" @click="closeMenu" />

      <!-- Panneau -->
      <section
        ref="panelRef"
        class="absolute inset-0 bg-white flex flex-col outline-none dark:bg-gray-900"
        tabindex="-1"
      >
        <!-- Header du drawer -->
        <div
          class="h-12 flex items-center justify-between px-3 border-b dark:border-gray-800"
        >
          <h2 class="text-sm font-semibold">Menu</h2>
          <button
            class="h-9 w-9 -mr-1 flex items-center justify-center rounded hover:bg-gray-100 active:scale-95 dark:hover:bg-gray-800"
            aria-label="Fermer le menu"
            @click="closeMenu"
          >
            <XMarkIcon class="w-6 h-6" />
          </button>
        </div>

        <!-- Contenu du drawer (squelette) -->
        <nav class="p-3 space-y-6 overflow-auto">
          <!-- Thème clair / sombre -->
          <button
            type="button"
            class="w-full flex items-center justify-between px-3 py-3 rounded border border-gray-200 hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            role="switch"
            :aria-checked="theme.isDark"
            @click="theme.toggle()"
          >
            <span class="flex items-center gap-2 text-sm font-medium">
              <MoonIcon
                v-if="theme.isDark"
                class="w-5 h-5"
                aria-hidden="true"
              />
              <SunIcon v-else class="w-5 h-5" aria-hidden="true" />
              <span>{{ theme.isDark ? "Thème sombre" : "Thème clair" }}</span>
            </span>
            <span
              class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors"
              :class="
                theme.isDark ? 'bg-indigo-600' : 'bg-gray-300 dark:bg-gray-600'
              "
            >
              <span
                class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                :class="theme.isDark ? 'translate-x-6' : 'translate-x-1'"
              />
            </span>
          </button>

          <!-- Non loggé : seulement Connexion / Inscription -->
          <div v-if="!isAuthenticated">
            <div
              class="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider dark:text-gray-400"
            >
              Compte
            </div>
            <ul class="space-y-1">
              <li>
                <RouterLink
                  class="block px-3 py-3 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                  to="/login"
                >
                  Connexion
                </RouterLink>
              </li>
              <li>
                <RouterLink
                  class="block px-3 py-3 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                  to="/register"
                >
                  Inscription
                </RouterLink>
              </li>
            </ul>
          </div>

          <!-- Loggé : tout le reste -->
          <template v-else>
            <div>
              <button
                class="w-full flex items-center justify-between px-2 py-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                :aria-expanded="openSections.account"
                @click="toggle('account')"
              >
                <span
                  class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider dark:text-gray-400"
                >
                  <UserCircleIcon class="w-4 h-4" aria-hidden="true" />
                  <span>Compte</span>
                </span>
              </button>
              <ul v-show="openSections.account" class="space-y-1">
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                    to="/profile/location"
                  >
                    <MapPinIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Mon profil</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                    to="/my/stats"
                  >
                    <ChartBarIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Mes stats</span>
                  </RouterLink>
                </li>
                <li>
                  <button
                    class="w-full text-left flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                    @click="doLogout"
                  >
                    <ArrowLeftOnRectangleIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Déconnexion</span>
                  </button>
                </li>
              </ul>
            </div>

            <!-- Caches -->
            <div>
              <button
                class="w-full flex items-center justify-between px-2 py-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                :aria-expanded="openSections.account"
                @click="toggle('caches')"
              >
                <span
                  class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider dark:text-gray-400"
                >
                  <MapPinIcon class="w-4 h-4" aria-hidden="true" />
                  <span>Caches</span>
                </span>
              </button>
              <ul v-show="openSections.caches" class="space-y-1">
                <li>
                  <RouterLink
                    to="/caches/import-gpx"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                  >
                    <DocumentArrowUpIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Importer GPX</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                    to="/caches/by-filter"
                  >
                    <AdjustmentsHorizontalIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Recherche (filtres)</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                    to="/caches/within-bbox"
                  >
                    <RectangleGroupIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Dans une BBox</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                    to="/caches/within-radius"
                  >
                    <RssIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Autour d’un point</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                    to="/caches/zones"
                  >
                    <GlobeEuropeAfricaIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Trouvées par zones</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                    to="/caches/zone-types"
                  >
                    <GlobeEuropeAfricaIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Types trouvés par zones</span>
                  </RouterLink>
                </li>
              </ul>
            </div>

            <!-- Challenges -->
            <div>
              <button
                class="w-full flex items-center justify-between px-2 py-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                :aria-expanded="openSections.account"
                @click="toggle('challenges')"
              >
                <span
                  class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider dark:text-gray-400"
                >
                  <Trophy class="w-4 h-4" aria-hidden="true" />
                  <span>Challenges</span>
                </span>
              </button>
              <ul v-show="openSections.challenges" class="space-y-1">
                <li>
                  <RouterLink
                    to="/my/challenges"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                  >
                    <Mountain
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Mes challenges</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/my/challenges/basics/matrix"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                  >
                    <Target
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Matrix D/T</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/my/challenges/basics/calendar"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                  >
                    <DocumentTextIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Calendar 365</span>
                  </RouterLink>
                </li>
              </ul>
            </div>

            <!-- Targets -->
            <div>
              <RouterLink
                to="/my/targets"
                class="w-full flex items-center px-2 py-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <span
                  class="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase tracking-wider dark:text-gray-400"
                >
                  <Target class="w-4 h-4" aria-hidden="true" />
                  <span>Targets</span>
                </span>
              </RouterLink>
            </div>

            <!-- Aide / FAQ -->
            <div>
              <button
                class="w-full flex items-center justify-between px-2 py-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                :aria-expanded="openSections.account"
                @click="toggle('help')"
              >
                <span
                  class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider dark:text-gray-400"
                >
                  <QuestionMarkCircleIcon class="w-4 h-4" aria-hidden="true" />
                  <span>Aide / FAQ</span>
                </span>
              </button>
              <ul v-show="openSections.help" class="space-y-1">
                <li>
                  <RouterLink
                    to="/help/user"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                  >
                    <UserCircleIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Compte</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/help/caches"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                  >
                    <MapPinIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Caches</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/help/challenges"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                  >
                    <Trophy
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Challenges</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/help/targets"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                  >
                    <Target
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Targets</span>
                  </RouterLink>
                </li>
              </ul>
            </div>
          </template>
        </nav>

        <footer class="border-t px-3 py-3 dark:border-gray-800">
          <RouterLink
            to="/legal"
            class="flex items-center gap-2 p-3 text-sm text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            <DocumentTextIcon class="w-4 h-4" aria-hidden="true" />
            <span>Mentions légales</span>
          </RouterLink>
        </footer>
      </section>
    </div>
  </div>
  <Toaster
    position="top-center"
    rich-colors
    close-button
    :theme="theme.isDark ? 'dark' : 'light'"
  />
</template>

<script setup lang="ts">
import logoUrl from "@/assets/brand/logo.svg";
import {
  ref,
  reactive,
  watch,
  onMounted,
  onBeforeUnmount,
  computed,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useAuthStore } from "@/store/auth";
import { useThemeStore } from "@/store/theme";
import {
  Bars3Icon,
  XMarkIcon,
  UserCircleIcon,
  ArrowLeftOnRectangleIcon,
  MapPinIcon,
  DocumentArrowUpIcon,
  AdjustmentsHorizontalIcon,
  RectangleGroupIcon,
  RssIcon,
  GlobeEuropeAfricaIcon,
  QuestionMarkCircleIcon,
  DocumentTextIcon,
  ChartBarIcon,
} from "@heroicons/vue/24/outline";
import {
  Mountain,
  Trophy,
  Target,
  Sun as SunIcon,
  Moon as MoonIcon,
} from "lucide-vue-next";
import { Toaster } from "vue-sonner";

const mainPadding = computed(() => (route.meta?.dense ? "p-0" : "p-3 md:p-4"));
const fabBottomPad = computed(() =>
  route.meta?.noFabPadding
    ? ""
    : "pb-[calc(3.5rem+max(1rem,env(safe-area-inset-bottom))+0.5rem)]",
);

const menuOpen = ref(false);
const panelRef = ref<HTMLElement | null>(null);

const route = useRoute();
const router = useRouter();

const auth = useAuthStore();
const { isAuthenticated } = storeToRefs(auth);
// init auth (refresh silent si possible)
auth.init().catch(() => {});

const theme = useThemeStore();
theme.init();

/** ---------- Accordéons par section ---------- */
type SectionKey = "account" | "caches" | "challenges" | "help" | "admin";
const openSections = reactive<Record<SectionKey, boolean>>({
  account: false,
  caches: false,
  challenges: false,
  help: false,
  admin: false,
});

function toggle(k: SectionKey) {
  openSections[k] = !openSections[k];
}

function openSectionForRoute(path: string) {
  // fermer tout
  (Object.keys(openSections) as SectionKey[]).forEach(
    (k) => (openSections[k] = false),
  );
  // ouvrir la section correspondant à la route
  if (/^\/(login|register|verify|resend|profile)/.test(path))
    openSections.account = true;
  else if (path.startsWith("/my/stats")) openSections.account = true;
  else if (path.startsWith("/caches")) openSections.caches = true;
  else if (path.startsWith("/my/challenges")) openSections.challenges = true;
  else if (path.startsWith("/help")) openSections.help = true;
  else openSections.account = true; // fallback sûr
}

onMounted(() => openSectionForRoute(route.fullPath));
watch(
  () => route.fullPath,
  (p) => openSectionForRoute(p),
);
// si on se déconnecte, on retombe logiquement sur "Compte"
watch(isAuthenticated, (ok) => {
  if (!ok) openSectionForRoute("/login");
});

/** ---------- Drawer ---------- */
function openMenu() {
  menuOpen.value = true;
  document.body.style.overflow = "hidden";
  requestAnimationFrame(() => panelRef.value?.focus());
}
function closeMenu() {
  menuOpen.value = false;
  document.body.style.overflow = "";
}
async function doLogout() {
  await auth.logout();
  closeMenu();
  router.replace("/login");
}

// Fermer le menu quand la route change
watch(
  () => route.fullPath,
  () => {
    if (menuOpen.value) closeMenu();
  },
);

// Sécurité : nettoyer le style body si le composant est démonté
onBeforeUnmount(() => {
  document.body.style.overflow = "";
});

// Écoute globale Esc (fallback)
onMounted(() => {
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape" && menuOpen.value) closeMenu();
  };
  window.addEventListener("keydown", onKey);
  onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
});
</script>
