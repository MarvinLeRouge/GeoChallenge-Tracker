<template>
  <div class="max-w-4xl mx-auto">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900 mb-2">
        Mes statistiques
      </h1>
      <p class="text-gray-600">
        Vue d'ensemble de votre activité géocaching
      </p>
    </div>

    <!-- Loading state -->
    <div
      v-if="loading"
      class="flex items-center justify-center py-12"
    >
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      <span class="ml-2 text-gray-600">Chargement de vos statistiques...</span>
    </div>

    <!-- Error state -->
    <div
      v-else-if="error"
      class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6"
    >
      <div class="flex">
        <ExclamationTriangleIcon class="h-5 w-5 text-red-400 mt-0.5" />
        <div class="ml-3">
          <h3 class="text-sm font-medium text-red-800">
            Erreur de chargement
          </h3>
          <p class="text-sm text-red-700 mt-1">
            {{ error }}
          </p>
          <button 
            class="mt-2 text-sm text-red-800 underline hover:text-red-900" 
            @click="loadStats"
          >
            Réessayer
          </button>
        </div>
      </div>
    </div>

    <!-- Stats content -->
    <div
      v-else-if="stats"
      class="space-y-6"
    >
      <!-- Cartes de statistiques principales -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Caches trouvées -->
        <div class="bg-white rounded-lg border border-gray-200 p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <MapPinIcon class="h-8 w-8 text-blue-600" />
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">
                Caches trouvées
              </p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ stats.total_caches_found }}
              </p>
            </div>
          </div>
        </div>

        <!-- Challenges totaux -->
        <div class="bg-white rounded-lg border border-gray-200 p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <Trophy class="h-8 w-8 text-yellow-600" />
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">
                Challenges
              </p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ stats.total_challenges }}
              </p>
            </div>
          </div>
        </div>

        <!-- Challenges actifs -->
        <div class="bg-white rounded-lg border border-gray-200 p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <PlayIcon class="h-8 w-8 text-green-600" />
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">
                En cours
              </p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ stats.active_challenges }}
              </p>
            </div>
          </div>
        </div>

        <!-- Challenges terminés -->
        <div class="bg-white rounded-lg border border-gray-200 p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <CheckCircleIcon class="h-8 w-8 text-emerald-600" />
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">
                Terminés
              </p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ stats.completed_challenges }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Informations détaillées -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Activité -->
        <div class="bg-white rounded-lg border border-gray-200 p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4 flex items-center">
            <CalendarIcon class="h-5 w-5 mr-2 text-gray-600" />
            Activité
          </h3>
          <div class="space-y-3">
            <div>
              <p class="text-sm font-medium text-gray-500">
                Compte créé le
              </p>
              <p class="text-sm text-gray-900">
                {{ formatDate(stats.created_at) }}
              </p>
            </div>
            <div v-if="stats.first_cache_found_at">
              <p class="text-sm font-medium text-gray-500">
                Première cache trouvée
              </p>
              <p class="text-sm text-gray-900">
                {{ formatDate(stats.first_cache_found_at) }}
              </p>
            </div>
            <div v-if="stats.last_cache_found_at">
              <p class="text-sm font-medium text-gray-500">
                Dernière cache trouvée
              </p>
              <p class="text-sm text-gray-900">
                {{ formatDate(stats.last_cache_found_at) }}
              </p>
            </div>
            <div v-if="stats.last_activity_at">
              <p class="text-sm font-medium text-gray-500">
                Dernière activité
              </p>
              <p class="text-sm text-gray-900">
                {{ formatDate(stats.last_activity_at) }}
              </p>
            </div>
          </div>
        </div>

        <!-- Progression -->
        <div class="bg-white rounded-lg border border-gray-200 p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4 flex items-center">
            <ChartBarIcon class="h-5 w-5 mr-2 text-gray-600" />
            Progression
          </h3>
          <div class="space-y-4">
            <!-- Ratio challenges terminés -->
            <div>
              <div class="flex justify-between text-sm">
                <span class="font-medium text-gray-500">Challenges terminés</span>
                <span class="text-gray-900">{{ completionRate }}%</span>
              </div>
              <div class="mt-1 relative">
                <div class="overflow-hidden h-2 text-xs flex rounded bg-gray-200">
                  <div 
                    :style="{ width: `${completionRate}%` }"
                    class="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-emerald-500 transition-all duration-500"
                  />
                </div>
              </div>
            </div>

            <!-- Jours depuis dernière cache -->
            <div v-if="stats.last_cache_found_at">
              <p class="text-sm font-medium text-gray-500">
                Jours depuis dernière cache
              </p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ daysSinceLastCache }}
              </p>
            </div>

            <!-- Moyenne caches par challenge actif -->
            <div v-if="stats.active_challenges > 0">
              <p class="text-sm font-medium text-gray-500">
                Caches par challenge actif
              </p>
              <p class="text-2xl font-semibold text-gray-900">
                {{ cachesPerActiveChallenge }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Statistiques par type de cache -->
      <div
        v-if="stats.cache_types_stats && stats.cache_types_stats.length > 0"
        class="bg-white rounded-lg border border-gray-200 p-6"
      >
        <h3 class="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <MapPinIcon class="h-5 w-5 mr-2 text-gray-600" />
          Répartition par type de cache
        </h3>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th
                  scope="col"
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Type de cache
                </th>
                <th
                  scope="col"
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Nombre trouvé
                </th>
                <th
                  scope="col"
                  class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  Pourcentage
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr
                v-for="typeStat in stats.cache_types_stats"
                :key="typeStat.type_id"
              >
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm font-medium text-gray-900">
                    {{ typeStat.type_label }}
                  </div>
                  <div class="text-sm text-gray-500">
                    {{ typeStat.type_code }}
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm text-gray-900">
                    {{ typeStat.count.toLocaleString('fr-FR') }}
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm text-gray-900">
                    {{ ((typeStat.count / stats.total_caches_found) * 100).toFixed(1) }}%
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
        class="bg-blue-50 border border-blue-200 rounded-lg p-4"
      >
        <div class="flex">
          <InformationCircleIcon class="h-5 w-5 text-blue-400 mt-0.5" />
          <div class="ml-3">
            <h3 class="text-sm font-medium text-blue-800">
              Prêt à commencer ?
            </h3>
            <p class="text-sm text-blue-700 mt-1">
              Importez vos premières caches via l'onglet "Caches" → "Importer GPX" pour voir vos statistiques évoluer !
            </p>
            <RouterLink 
              to="/caches/import-gpx"
              class="mt-2 inline-flex text-sm text-blue-800 underline hover:text-blue-900"
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
import { onMounted } from 'vue'
import { useUserStats } from '@/composables/useUserStats'
import {
  MapPinIcon,
  ExclamationTriangleIcon,
  CalendarIcon,
  ChartBarIcon,
  InformationCircleIcon,
  PlayIcon,
  CheckCircleIcon
} from '@heroicons/vue/24/outline'
import { Trophy } from 'lucide-vue-next'

const { stats, loading, error, loadStats, completionRate, daysSinceLastCache, cachesPerActiveChallenge } = useUserStats()

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

onMounted(() => {
  loadStats()
})
</script>