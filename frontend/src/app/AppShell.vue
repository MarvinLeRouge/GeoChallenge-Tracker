<template>
  <div class="min-h-screen flex flex-col bg-white text-gray-900">
    <!-- Header minimal -->
    <header class="flex items-center justify-between px-3 py-2 border-b">
      <RouterLink
        to="/"
        class="flex items-center gap-2 -m-2 px-3 py-2 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
        aria-label="Accueil"
      >
        <img
          :src="logoUrl"
          alt="GeoChallenge Tracker"
          class="h-11 w-auto"
        >
        <span class="text-lg font-semibold">GC Tracker</span>
      </RouterLink>
      <div
        aria-hidden="true"
        class="w-6 h-6"
      />
    </header>

    <!-- Contenu -->
    <main
      :class="[mainPadding, fabBottomPad]"
      class="flex-1 min-h-0 relative"
    >
      <RouterView />
    </main>

    <!-- FAB (menu trigger) -->
    <button
      class="fixed bottom-[max(1rem,env(safe-area-inset-bottom))] right-[max(1rem,env(safe-area-inset-right))] z-50
             h-14 w-14 rounded-full shadow-lg border border-gray-200 bg-white
             flex items-center justify-center active:scale-95 transition"
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
      <div
        class="absolute inset-0 bg-black/40"
        @click="closeMenu"
      />

      <!-- Panneau -->
      <section
        ref="panelRef"
        class="absolute inset-0 bg-white flex flex-col outline-none"
        tabindex="-1"
      >
        <!-- Header du drawer -->
        <div class="h-12 flex items-center justify-between px-3 border-b">
          <h2 class="text-sm font-semibold">
            Menu
          </h2>
          <button
            class="h-9 w-9 -mr-1 flex items-center justify-center rounded hover:bg-gray-100 active:scale-95"
            aria-label="Fermer le menu"
            @click="closeMenu"
          >
            <XMarkIcon class="w-6 h-6" />
          </button>
        </div>

        <!-- Contenu du drawer (squelette) -->
        <nav class="p-3 space-y-6 overflow-auto">
          <!-- Non loggé : seulement Connexion / Inscription -->
          <div v-if="!isAuthenticated">
            <div class="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">
              Compte
            </div>
            <ul class="space-y-1">
              <li>
                <RouterLink
                  class="block px-3 py-3 rounded hover:bg-gray-100"
                  to="/login"
                >
                  Connexion
                </RouterLink>
              </li>
              <li>
                <RouterLink
                  class="block px-3 py-3 rounded hover:bg-gray-100"
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
                class="w-full flex items-center justify-between px-2 py-2 rounded hover:bg-gray-100"
                :aria-expanded="openSections.account"
                @click="toggle('account')"
              >
                <span class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">
                  <UserCircleIcon
                    class="w-4 h-4"
                    aria-hidden="true"
                  />
                  <span>Compte</span>
                </span>
              </button>
              <ul
                v-show="openSections.account"
                class="space-y-1"
              >
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                    to="/profile/location"
                  >
                    <MapPinIcon
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Mon profil</span>
                  </RouterLink>
                </li>
                <li>
                  <button
                    class="w-full text-left flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                    @click="doLogout"
                  >
                    <ArrowLeftOnRectangleIcon
                      class="w-5 h-5 shrink-0 text-gray-700"
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
                class="w-full flex items-center justify-between px-2 py-2 rounded hover:bg-gray-100"
                :aria-expanded="openSections.account"
                @click="toggle('caches')"
              >
                <span class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">
                  <MapPinIcon
                    class="w-4 h-4"
                    aria-hidden="true"
                  />
                  <span>Caches</span>
                </span>
              </button>
              <ul
                v-show="openSections.caches"
                class="space-y-1"
              >
                <li>
                  <RouterLink
                    to="/caches/import-gpx"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                  >
                    <DocumentArrowUpIcon
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Importer GPX</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                    to="/caches/by-filter"
                  >
                    <AdjustmentsHorizontalIcon
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Recherche (filtres)</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                    to="/caches/within-bbox"
                  >
                    <RectangleGroupIcon
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Dans une BBox</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                    to="/caches/within-radius"
                  >
                    <RssIcon
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Autour d’un point</span>
                  </RouterLink>
                </li>
              </ul>
            </div>

            <!-- Challenges -->
            <div>
              <button
                class="w-full flex items-center justify-between px-2 py-2 rounded hover:bg-gray-100"
                :aria-expanded="openSections.account"
                @click="toggle('challenges')"
              >
                <span class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">
                  <Trophy
                    class="w-4 h-4"
                    aria-hidden="true"
                  />
                  <span>Challenges</span>
                </span>
              </button>
              <ul
                v-show="openSections.challenges"
                class="space-y-1"
              >
                <li>
                  <RouterLink
                    to="/my/challenges/sync"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                  >
                    <ArrowPathIcon
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Synchroniser</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/my/challenges/list"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                  >
                    <Mountain
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Mes challenges</span>
                  </RouterLink>
                </li>
              </ul>
            </div>

            <!-- Targets -->
            <div>
              <button
                class="w-full flex items-center justify-between px-2 py-2 rounded hover:bg-gray-100"
                :aria-expanded="openSections.account"
                @click="toggle('targets')"
              >
                <span class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">
                  <Target
                    class="w-4 h-4"
                    aria-hidden="true"
                  />
                  <span>Targets</span>
                </span>
              </button>
              <ul
                v-show="openSections.targets"
                class="space-y-1"
              >
                <li>
                  <RouterLink
                    to="/my/targets"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                  >
                    <Target
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Tous mes targets</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/my/targets/nearby"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                  >
                    <LocateFixed
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>À proximité</span>
                  </RouterLink>
                </li>
              </ul>
            </div>

            <!-- Aide / FAQ -->
            <div>
              <button
                class="w-full flex items-center justify-between px-2 py-2 rounded hover:bg-gray-100"
                :aria-expanded="openSections.account"
                @click="toggle('help')"
              >
                <span class="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">
                  <QuestionMarkCircleIcon
                    class="w-4 h-4"
                    aria-hidden="true"
                  />
                  <span>Aide / FAQ</span>
                </span>
              </button>
              <ul
                v-show="openSections.help"
                class="space-y-1"
              >
                <li>
                  <RouterLink
                    to="/help/user"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                  >
                    <UserCircleIcon
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Compte</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/help/caches"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                  >
                    <MapPinIcon
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Caches</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/help/challenges"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                  >
                    <Trophy
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Challenges</span>
                  </RouterLink>
                </li>
                <li>
                  <RouterLink
                    to="/help/targets"
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300"
                  >
                    <Target
                      class="w-5 h-5 shrink-0 text-gray-700"
                      aria-hidden="true"
                    />
                    <span>Targets</span>
                  </RouterLink>
                </li>
              </ul>
            </div>
          </template>
        </nav>

        <footer class="border-t px-3 py-3">
          <RouterLink
            to="/legal"
            class="flex items-center gap-2 p-3 text-sm text-darkgray-500 hover:bg-gray-100"
          >
            <DocumentTextIcon
              class="w-4 h-4"
              aria-hidden="true"
            />
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
  />
</template>

<script setup lang="ts">
import logoUrl from '@/assets/brand/logo.svg'
import { ref, reactive, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/store/auth'
import {
  Bars3Icon, XMarkIcon, UserCircleIcon, ArrowLeftOnRectangleIcon, MapPinIcon,
  DocumentArrowUpIcon, AdjustmentsHorizontalIcon, RectangleGroupIcon, RssIcon,
  ArrowPathIcon, QuestionMarkCircleIcon,
  DocumentTextIcon
} from '@heroicons/vue/24/outline'
import { Mountain, Trophy, Target, LocateFixed } from 'lucide-vue-next'
import { Toaster } from 'vue-sonner'

const mainPadding = computed(() => (route.meta?.dense ? 'p-0' : 'p-3 md:p-4'))
const fabBottomPad = computed(() =>
  route.meta?.noFabPadding ? '' : 'pb-[calc(3.5rem+max(1rem,env(safe-area-inset-bottom))+0.5rem)]'
)

const menuOpen = ref(false)
const panelRef = ref<HTMLElement | null>(null)

const route = useRoute()
const router = useRouter()

const auth = useAuthStore()
const { isAuthenticated } = storeToRefs(auth)
// init auth (refresh silent si possible)
auth.init().catch(() => { })

/** ---------- Accordéons par section ---------- */
type SectionKey = 'account' | 'caches' | 'challenges' | 'targets' | 'help' | 'admin'
const openSections = reactive<Record<SectionKey, boolean>>({
  account: false,
  caches: false,
  challenges: false,
  targets: false,
  help: false,
  admin: false,
})

function toggle(k: SectionKey) {
  openSections[k] = !openSections[k]
}

function openSectionForRoute(path: string) {
  // fermer tout
  ; (Object.keys(openSections) as SectionKey[]).forEach(k => (openSections[k] = false))
  // ouvrir la section correspondant à la route
  if (/^\/(login|register|verify|resend|profile)/.test(path)) openSections.account = true
  else if (path.startsWith('/caches')) openSections.caches = true
  else if (path.startsWith('/my/challenges')) openSections.challenges = true
  else if (path.startsWith('/my/targets')) openSections.targets = true
  else if (path.startsWith('/help')) openSections.help = true
  else openSections.account = true // fallback sûr
}

onMounted(() => openSectionForRoute(route.fullPath))
watch(() => route.fullPath, (p) => openSectionForRoute(p))
// si on se déconnecte, on retombe logiquement sur "Compte"
watch(isAuthenticated, (ok) => { if (!ok) openSectionForRoute('/login') })

/** ---------- Drawer ---------- */
function openMenu() {
  menuOpen.value = true
  document.body.style.overflow = 'hidden'
  requestAnimationFrame(() => panelRef.value?.focus())
}
function closeMenu() {
  menuOpen.value = false
  document.body.style.overflow = ''
}
function doLogout() {
  auth.logout()
  closeMenu()
  router.replace('/login')
}

// Fermer le menu quand la route change
watch(() => route.fullPath, () => {
  if (menuOpen.value) closeMenu()
})

// Sécurité : nettoyer le style body si le composant est démonté
onBeforeUnmount(() => { document.body.style.overflow = '' })

// Écoute globale Esc (fallback)
onMounted(() => {
  const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && menuOpen.value) closeMenu() }
  window.addEventListener('keydown', onKey)
  onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
})
</script>
