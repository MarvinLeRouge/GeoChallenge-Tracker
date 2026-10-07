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
      @click="drawerRef?.open()"
    >
      <Bars3Icon class="w-7 h-7" />
      <span class="sr-only">Menu</span>
    </button>

    <AppShellMenuDrawer ref="drawerRef" />
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
import { ref, computed } from "vue";
import { useRoute } from "vue-router";
import { useAuthStore } from "@/store/auth";
import { useThemeStore } from "@/store/theme";
import { Bars3Icon } from "@heroicons/vue/24/outline";
import { Toaster } from "vue-sonner";
import AppShellMenuDrawer from "@/app/AppShellMenuDrawer.vue";

const route = useRoute();

const mainPadding = computed(() => (route.meta?.dense ? "p-0" : "p-3 md:p-4"));
const fabBottomPad = computed(() =>
  route.meta?.noFabPadding
    ? ""
    : "pb-[calc(3.5rem+max(1rem,env(safe-area-inset-bottom))+0.5rem)]",
);

const drawerRef = ref<InstanceType<typeof AppShellMenuDrawer> | null>(null);

const auth = useAuthStore();
// init auth (refresh silent si possible)
auth.init().catch(() => {});

const theme = useThemeStore();
theme.init();
</script>
