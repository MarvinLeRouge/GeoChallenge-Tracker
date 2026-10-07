<template>
  <!-- Drawer plein écran (custom, accessible) -->
  <div
    v-if="menuOpen"
    class="fixed inset-0 z-50"
    role="dialog"
    aria-modal="true"
    @keydown.esc="close"
  >
    <!-- Overlay -->
    <div class="absolute inset-0 bg-black/40" @click="close" />

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
          @click="close"
        >
          <XMarkIcon class="w-6 h-6" />
        </button>
      </div>

      <!-- Contenu du drawer (squelette) -->
      <AppShellMenuNav @logout="handleLogout" />

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
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth";
import { XMarkIcon, DocumentTextIcon } from "@heroicons/vue/24/outline";
import AppShellMenuNav from "@/app/AppShellMenuNav.vue";

const menuOpen = ref(false);
const panelRef = ref<HTMLElement | null>(null);

const route = useRoute();
const router = useRouter();

const auth = useAuthStore();

/** ---------- Drawer ---------- */
function open() {
  menuOpen.value = true;
  document.body.style.overflow = "hidden";
  requestAnimationFrame(() => panelRef.value?.focus());
}
function close() {
  menuOpen.value = false;
  document.body.style.overflow = "";
}
async function handleLogout() {
  await auth.logout();
  close();
  router.replace("/login");
}

defineExpose({ open, close });

// Fermer le menu quand la route change
watch(
  () => route.fullPath,
  () => {
    if (menuOpen.value) close();
  },
);

// Sécurité : nettoyer le style body si le composant est démonté
onBeforeUnmount(() => {
  document.body.style.overflow = "";
});

// Écoute globale Esc (fallback)
onMounted(() => {
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape" && menuOpen.value) close();
  };
  window.addEventListener("keydown", onKey);
  onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
});
</script>
