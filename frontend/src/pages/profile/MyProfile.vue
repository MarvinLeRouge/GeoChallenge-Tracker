<template>
  <div class="max-w-4xl mx-auto">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900 mb-2 dark:text-gray-100">
        Mon profil
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        Gérez vos informations personnelles et votre localisation
      </p>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="py-12">
      <LoadingIndicator label="Chargement du profil…" />
    </div>

    <!-- Error state -->
    <div
      v-else-if="error"
      class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 dark:bg-red-950 dark:border-red-900"
    >
      <div class="flex">
        <ExclamationTriangleIcon
          class="h-5 w-5 text-red-400 mt-0.5 dark:text-red-500"
        />
        <div class="ml-3">
          <h3 class="text-sm font-medium text-red-800 dark:text-red-300">
            Erreur de chargement
          </h3>
          <p class="text-sm text-red-700 mt-1 dark:text-red-400">
            {{ error }}
          </p>
          <button
            class="mt-2 text-sm text-red-800 underline hover:text-red-900 dark:text-red-300 dark:hover:text-red-200"
            @click="loadProfile"
          >
            Réessayer
          </button>
        </div>
      </div>
    </div>

    <!-- Profile content -->
    <div v-else-if="profile" class="space-y-6">
      <!-- Informations personnelles -->
      <div>
        <h3
          class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center dark:text-gray-400"
        >
          <UserCircleIcon class="h-4 w-4 mr-1.5" />
          Informations personnelles
        </h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label
              class="block text-sm font-medium text-gray-500 mb-1 dark:text-gray-400"
            >
              Nom d'utilisateur
            </label>
            <p
              class="text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded dark:text-gray-100 dark:bg-gray-900"
            >
              {{ profile.username }}
            </p>
          </div>
          <div>
            <label
              class="block text-sm font-medium text-gray-500 mb-1 dark:text-gray-400"
            >
              Adresse e-mail
            </label>
            <p
              class="text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded dark:text-gray-100 dark:bg-gray-900"
            >
              {{ profile.email }}
            </p>
          </div>
        </div>
      </div>

      <!-- Préférences -->
      <div>
        <h3
          class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center dark:text-gray-400"
        >
          <AdjustmentsHorizontalIcon class="h-4 w-4 mr-1.5" />
          Préférences
        </h3>

        <button
          type="button"
          class="w-full flex items-center justify-between px-3 py-3 rounded border border-gray-200 hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-700"
          role="switch"
          :aria-checked="theme.isDark"
          @click="theme.toggle()"
        >
          <span
            class="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-gray-100"
          >
            <MoonIcon v-if="theme.isDark" class="w-5 h-5" aria-hidden="true" />
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
      </div>

      <ProfileLocationCard
        :location="location"
        :has-location="!!hasLocation"
        :location-string="locationString"
        :saving="saving"
        :save-error="saveError"
        :update-location="updateLocation"
      />

      <ProfileFoundCachesSync />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useUserProfile } from "@/composables/useUserProfile";
import { useThemeStore } from "@/store/theme";
import LoadingIndicator from "@/components/ui/LoadingIndicator.vue";
import ProfileLocationCard from "@/components/profile/ProfileLocationCard.vue";
import ProfileFoundCachesSync from "@/components/profile/ProfileFoundCachesSync.vue";
import {
  UserCircleIcon,
  ExclamationTriangleIcon,
  AdjustmentsHorizontalIcon,
} from "@heroicons/vue/24/outline";
import { Sun as SunIcon, Moon as MoonIcon } from "lucide-vue-next";

const theme = useThemeStore();

const {
  profile,
  location,
  loading,
  error,
  saving,
  saveError,
  loadProfile,
  updateLocation,
  hasLocation,
  locationString,
} = useUserProfile();

onMounted(async () => {
  await loadProfile();
});
</script>
