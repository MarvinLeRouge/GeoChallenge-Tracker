<template>
  <div class="max-w-4xl mx-auto">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900 mb-2 dark:text-gray-100">
        Mes statistiques
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        Vue d'ensemble de votre activité géocaching
      </p>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-gray-100"
      />
      <span class="ml-2 text-gray-600 dark:text-gray-400"
        >Chargement de vos statistiques...</span
      >
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
            @click="loadStats"
          >
            Réessayer
          </button>
        </div>
      </div>
    </div>

    <!-- Stats content -->
    <div v-else-if="stats" class="space-y-6">
      <!-- Cartes de statistiques principales -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Caches trouvées -->
        <div class="bg-gray-100 p-3 rounded-lg dark:bg-gray-900">
          <div class="flex items-center gap-2">
            <MapPinIcon
              class="h-6 w-6 text-gray-500 shrink-0 dark:text-gray-400"
              aria-hidden="true"
            />
            <div>
              <div class="text-2xl font-bold text-gray-800 dark:text-gray-200">
                {{ stats.total_caches_found }}
              </div>
              <div class="text-sm text-gray-600 dark:text-gray-400">
                Caches trouvées
              </div>
            </div>
          </div>
        </div>

        <!-- Challenges totaux -->
        <div class="bg-gray-100 p-3 rounded-lg dark:bg-gray-900">
          <div class="flex items-center gap-2">
            <Trophy
              class="h-6 w-6 text-gray-500 shrink-0 dark:text-gray-400"
              aria-hidden="true"
            />
            <div>
              <div class="text-2xl font-bold text-gray-800 dark:text-gray-200">
                {{ stats.total_challenges }}
              </div>
              <div class="text-sm text-gray-600 dark:text-gray-400">
                Challenges
              </div>
            </div>
          </div>
        </div>

        <!-- Challenges actifs -->
        <div class="bg-gray-100 p-3 rounded-lg dark:bg-gray-900">
          <div class="flex items-center gap-2">
            <PlayIcon
              class="h-6 w-6 text-gray-500 shrink-0 dark:text-gray-400"
              aria-hidden="true"
            />
            <div>
              <div class="text-2xl font-bold text-gray-800 dark:text-gray-200">
                {{ stats.active_challenges }}
              </div>
              <div class="text-sm text-gray-600 dark:text-gray-400">
                En cours
              </div>
            </div>
          </div>
        </div>

        <!-- Challenges terminés -->
        <div class="bg-green-50 p-3 rounded-lg dark:bg-green-950">
          <div class="flex items-center gap-2">
            <CheckCircleIcon
              class="h-6 w-6 text-green-600 shrink-0 dark:text-green-400"
              aria-hidden="true"
            />
            <div>
              <div
                class="text-2xl font-bold text-green-800 dark:text-green-300"
              >
                {{ stats.completed_challenges }}
              </div>
              <div class="text-sm text-green-700 dark:text-green-400">
                Terminés
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Informations détaillées -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Activité -->
        <div
          class="bg-white rounded-lg border border-gray-200 p-6 dark:bg-gray-800 dark:border-gray-700"
        >
          <h3
            class="text-lg font-medium text-gray-900 mb-4 flex items-center dark:text-gray-100"
          >
            <CalendarIcon class="h-5 w-5 mr-2 text-gray-600" />
            Activité
          </h3>
          <div class="space-y-3">
            <div>
              <p class="text-sm font-medium text-gray-500 dark:text-gray-400">
                Compte créé le
              </p>
              <p class="text-sm text-gray-900 dark:text-gray-100">
                {{ formatDate(stats.created_at) }}
              </p>
            </div>
            <div v-if="stats.first_cache_found_at">
              <p class="text-sm font-medium text-gray-500 dark:text-gray-400">
                Première cache trouvée
              </p>
              <p class="text-sm text-gray-900 dark:text-gray-100">
                {{ formatDate(stats.first_cache_found_at) }}
              </p>
            </div>
            <div v-if="stats.last_cache_found_at">
              <p class="text-sm font-medium text-gray-500 dark:text-gray-400">
                Dernière cache trouvée
              </p>
              <p class="text-sm text-gray-900 dark:text-gray-100">
                {{ formatDate(stats.last_cache_found_at) }}
              </p>
            </div>
            <div v-if="stats.last_activity_at">
              <p class="text-sm font-medium text-gray-500 dark:text-gray-400">
                Dernière activité
              </p>
              <p class="text-sm text-gray-900 dark:text-gray-100">
                {{ formatDate(stats.last_activity_at) }}
              </p>
            </div>
          </div>
        </div>

        <!-- Progression -->
        <div
          class="bg-white rounded-lg border border-gray-200 p-6 dark:bg-gray-800 dark:border-gray-700"
        >
          <h3
            class="text-lg font-medium text-gray-900 mb-4 flex items-center dark:text-gray-100"
          >
            <ChartBarIcon class="h-5 w-5 mr-2 text-gray-600" />
            Progression
          </h3>
          <div class="space-y-4">
            <!-- Ratio challenges terminés -->
            <div>
              <div class="flex justify-between text-sm">
                <span class="font-medium text-gray-500 dark:text-gray-400"
                  >Challenges terminés</span
                >
                <span class="text-gray-900 dark:text-gray-100"
                  >{{ completionRate }}%</span
                >
              </div>
              <div class="mt-1 relative">
                <div
                  class="overflow-hidden h-2 text-xs flex rounded bg-gray-200 dark:bg-gray-700"
                >
                  <div
                    :style="{ width: `${completionRate}%` }"
                    class="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-emerald-500 transition-all duration-500"
                  />
                </div>
              </div>
            </div>

            <!-- Jours depuis dernière cache -->
            <div v-if="stats.last_cache_found_at">
              <p class="text-sm font-medium text-gray-500 dark:text-gray-400">
                Jours depuis dernière cache
              </p>
              <p
                class="text-2xl font-semibold text-gray-900 dark:text-gray-100"
              >
                {{ daysSinceLastCache }}
              </p>
            </div>

            <!-- Moyenne caches par challenge actif -->
            <div v-if="stats.active_challenges > 0">
              <p class="text-sm font-medium text-gray-500 dark:text-gray-400">
                Caches par challenge actif
              </p>
              <p
                class="text-2xl font-semibold text-gray-900 dark:text-gray-100"
              >
                {{ cachesPerActiveChallenge }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Statistiques par type de cache -->
      <div
        v-if="stats.cache_types_stats && stats.cache_types_stats.length > 0"
        class="bg-white rounded-lg border border-gray-200 p-6 dark:bg-gray-800 dark:border-gray-700"
      >
        <h3
          class="text-lg font-medium text-gray-900 mb-4 flex items-center dark:text-gray-100"
        >
          <MapPinIcon class="h-5 w-5 mr-2 text-gray-600" />
          Répartition par type de cache
        </h3>
        <div class="overflow-x-auto">
          <table
            class="min-w-full divide-y divide-gray-200 dark:divide-gray-700"
          >
            <thead class="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th
                  scope="col"
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400"
                >
                  Type de cache
                </th>
                <th
                  scope="col"
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400"
                >
                  Nombre trouvé
                </th>
                <th
                  scope="col"
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400"
                >
                  Pourcentage
                </th>
              </tr>
            </thead>
            <tbody
              class="bg-white divide-y divide-gray-200 dark:bg-gray-800 dark:divide-gray-700"
            >
              <tr
                v-for="typeStat in stats.cache_types_stats"
                :key="typeStat.type_id"
              >
                <td class="px-6 py-4 whitespace-nowrap">
                  <div
                    class="text-sm font-medium text-gray-900 dark:text-gray-100"
                  >
                    {{ typeStat.type_label }}
                  </div>
                  <div class="text-sm text-gray-500 dark:text-gray-400">
                    {{ typeStat.type_code }}
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm text-gray-900 dark:text-gray-100">
                    {{ typeStat.count.toLocaleString("fr-FR") }}
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm text-gray-900 dark:text-gray-100">
                    {{
                      (
                        (typeStat.count / stats.total_caches_found) *
                        100
                      ).toFixed(1)
                    }}%
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Message d'encouragement -->
      <div
        v-if="stats.total_caches_found === 0"
        class="bg-blue-50 border border-blue-200 rounded-lg p-4 dark:bg-blue-950 dark:border-blue-900"
      >
        <div class="flex">
          <InformationCircleIcon
            class="h-5 w-5 text-blue-400 mt-0.5 dark:text-blue-500"
          />
          <div class="ml-3">
            <h3 class="text-sm font-medium text-blue-800 dark:text-blue-300">
              Prêt à commencer ?
            </h3>
            <p class="text-sm text-blue-700 mt-1 dark:text-blue-400">
              Importez vos premières caches via l'onglet "Caches" → "Importer
              GPX" pour voir vos statistiques évoluer !
            </p>
            <RouterLink
              to="/caches/import-gpx"
              class="mt-2 inline-flex text-sm text-blue-800 underline hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-200"
            >
              Importer des caches →
            </RouterLink>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useUserStats } from "@/composables/useUserStats";
import {
  MapPinIcon,
  ExclamationTriangleIcon,
  CalendarIcon,
  ChartBarIcon,
  InformationCircleIcon,
  PlayIcon,
  CheckCircleIcon,
} from "@heroicons/vue/24/outline";
import { Trophy } from "lucide-vue-next";

const {
  stats,
  loading,
  error,
  loadStats,
  completionRate,
  daysSinceLastCache,
  cachesPerActiveChallenge,
} = useUserStats();

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("fr-FR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

onMounted(() => {
  loadStats();
});
</script>
