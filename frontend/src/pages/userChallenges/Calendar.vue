<template>
  <div class="p-4 space-y-4">
    <!-- En-tête -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">Calendar Challenge</h1>
        <p class="text-gray-600">Vérification de completion des 365/366 jours de l'année</p>
      </div>
    </div>

    <!-- Filtres -->
    <div class="rounded-lg border bg-white p-4 shadow-sm">
      <h2 class="font-semibold mb-3">Filtres</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Type de cache</label>
          <select 
            v-model="selectedCacheType" 
            class="w-full border rounded px-3 py-2 bg-white"
            @change="fetchCalendar"
          >
            <option value="">Tous les types</option>
            <option 
              v-for="type in sortedCacheTypes" 
              :key="type._id" 
              :value="type.code"
            >
              {{ type.name }} ({{ type.code }})
            </option>
          </select>
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Taille de cache</label>
          <select 
            v-model="selectedCacheSize" 
            class="w-full border rounded px-3 py-2 bg-white"
            @change="fetchCalendar"
          >
            <option value="">Toutes les tailles</option>
            <option 
              v-for="size in sortedCacheSizes" 
              :key="size._id" 
              :value="size.code"
            >
              {{ size.name }} ({{ size.code }})
            </option>
          </select>
        </div>
      </div>
    </div>

    <!-- Loading/Error -->
    <div v-if="loading" class="text-center text-gray-500 py-8">
      Chargement du calendrier...
    </div>
    <div v-if="error" class="text-center text-red-600 text-sm py-4 bg-red-50 rounded-lg">
      {{ error }}
    </div>

    <!-- Résultats Calendar -->
    <div v-if="calendarResult && !loading" class="space-y-4">
      <!-- Statistiques -->
      <div class="rounded-lg border bg-white p-4 shadow-sm">
        <h2 class="font-semibold mb-3">Résumé</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="bg-green-50 p-3 rounded-lg">
            <div class="text-2xl font-bold text-green-800">
              {{ calendarResult.completed_days.length }}
            </div>
            <div class="text-sm text-green-600">
              Jours complétés
            </div>
          </div>
          <div class="bg-blue-50 p-3 rounded-lg">
            <div class="text-2xl font-bold text-blue-800">
              {{ (calendarResult.completion_rate_365 * 100).toFixed(1) }}%
            </div>
            <div class="text-sm text-blue-600">
              Completion 365 jours
            </div>
          </div>
          <div class="bg-purple-50 p-3 rounded-lg">
            <div class="text-2xl font-bold text-purple-800">
              {{ (calendarResult.completion_rate_366 * 100).toFixed(1) }}%
            </div>
            <div class="text-sm text-purple-600">
              Completion 366 jours (bissextile)
            </div>
          </div>
        </div>
      </div>

      <!-- Calendrier visuel -->
      <div class="rounded-lg border bg-white p-4 shadow-sm">
        <h2 class="font-semibold mb-3">Calendrier annuel</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <div v-for="month in 12" :key="month" class="border rounded-lg p-2">
            <h3 class="text-sm font-medium text-center mb-2">
              {{ monthNames[month - 1] }}
            </h3>
            <div class="grid grid-cols-7 gap-1 text-xs">
              <!-- Jours du mois -->
              <div 
                v-for="day in getDaysInMonth(month)"
                :key="`${month}-${day}`"
                class="w-6 h-6 flex items-center justify-center rounded text-xs"
                :class="getDayClass(month, day)"
                :title="getDayTitle(month, day)"
              >
                {{ day }}
              </div>
            </div>
            <!-- Jours manquants ce mois -->
            <div v-if="getMissingDaysCount(month) > 0" class="text-xs text-red-600 mt-1">
              {{ getMissingDaysCount(month) }} jour{{ getMissingDaysCount(month) > 1 ? 's' : '' }} manquant{{ getMissingDaysCount(month) > 1 ? 's' : '' }}
            </div>
          </div>
        </div>
        
        <!-- Légende -->
        <div class="mt-4 flex flex-wrap gap-4 text-xs">
          <div class="flex items-center gap-1">
            <div class="w-4 h-4 bg-green-200 rounded"></div>
            <span>Jour complété</span>
          </div>
          <div class="flex items-center gap-1">
            <div class="w-4 h-4 bg-red-200 rounded"></div>
            <span>Jour manquant</span>
          </div>
          <div class="flex items-center gap-1">
            <div class="w-4 h-4 bg-gray-100 rounded"></div>
            <span>Jour sans cache</span>
          </div>
        </div>
      </div>

      <!-- Statistiques détaillées par mois -->
      <div class="rounded-lg border bg-white p-4 shadow-sm">
        <h2 class="font-semibold mb-3">Détails par mois</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div 
            v-for="month in 12" 
            :key="month"
            class="border rounded-lg p-3"
          >
            <h3 class="font-medium">{{ monthNames[month - 1] }}</h3>
            <div class="mt-2 space-y-1 text-sm">
              <div class="flex justify-between">
                <span>Complétés:</span>
                <span class="text-green-600 font-medium">
                  {{ getCompletedDaysInMonth(month) }}/{{ getDaysInMonth(month) }}
                </span>
              </div>
              <div class="flex justify-between">
                <span>Manquants:</span>
                <span class="text-red-600 font-medium">
                  {{ getMissingDaysCount(month) }}
                </span>
              </div>
              <div class="flex justify-between">
                <span>Taux:</span>
                <span class="font-medium">
                  {{ ((getCompletedDaysInMonth(month) / getDaysInMonth(month)) * 100).toFixed(1) }}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/api/http'
import type { CalendarResult, CacheType, CacheSize } from '@/types/challenges'

const loading = ref(false)
const error = ref('')
const calendarResult = ref<CalendarResult | null>(null)
const cacheTypes = ref<CacheType[]>([])
const cacheSizes = ref<CacheSize[]>([])
const selectedCacheType = ref('')
const selectedCacheSize = ref('')

const monthNames = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
]

// Tri alphabétique des types de cache
const sortedCacheTypes = computed(() => {
  return [...cacheTypes.value].sort((a, b) => a.name.localeCompare(b.name))
})

// Tri des tailles par ordre logique
const sortedCacheSizes = computed(() => {
  const sizeOrder = ['Micro', 'Small', 'Regular', 'Large', 'Other']
  return [...cacheSizes.value].sort((a, b) => {
    const aIndex = sizeOrder.indexOf(a.name)
    const bIndex = sizeOrder.indexOf(b.name)
    return aIndex - bIndex
  })
})

function getDaysInMonth(month: number): number {
  // Retourne le nombre de jours dans le mois (maximum pour année bissextile)
  const daysInMonth = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return daysInMonth[month - 1]
}

function isCompletedDay(month: number, day: number): boolean {
  if (!calendarResult.value) return false
  return calendarResult.value.completed_days.some(d => d.month === month && d.day === day)
}

function getDayCount(month: number, day: number): number {
  if (!calendarResult.value) return 0
  const dayData = calendarResult.value.completed_days.find(d => d.month === month && d.day === day)
  return dayData?.count || 0
}

function getDayClass(month: number, day: number): string {
  if (isCompletedDay(month, day)) {
    return 'bg-green-200 text-green-800'
  } else if (isMissingDay(month, day)) {
    return 'bg-red-200 text-red-800'
  } else {
    return 'bg-gray-100 text-gray-600'
  }
}

function getDayTitle(month: number, day: number): string {
  const count = getDayCount(month, day)
  if (count > 0) {
    return `${day}/${month} - ${count} cache${count > 1 ? 's' : ''}`
  } else if (isMissingDay(month, day)) {
    return `${day}/${month} - Jour manquant`
  } else {
    return `${day}/${month}`
  }
}

function isMissingDay(month: number, day: number): boolean {
  if (!calendarResult.value) return false
  const missingDays = calendarResult.value.missing_days_by_month[month]
  return missingDays?.includes(day) || false
}

function getMissingDaysCount(month: number): number {
  if (!calendarResult.value) return 0
  return calendarResult.value.missing_days_by_month[month]?.length || 0
}

function getCompletedDaysInMonth(month: number): number {
  if (!calendarResult.value) return 0
  return calendarResult.value.completed_days.filter(d => d.month === month).length
}

async function fetchCacheTypes() {
  try {
    const response = await api.get('/cache_types')
    cacheTypes.value = response.data
  } catch (e: any) {
    console.error('Erreur chargement types:', e)
  }
}

async function fetchCacheSizes() {
  try {
    const response = await api.get('/cache_sizes')
    cacheSizes.value = response.data
  } catch (e: any) {
    console.error('Erreur chargement tailles:', e)
  }
}

async function fetchCalendar() {
  loading.value = true
  error.value = ''
  
  try {
    const params = new URLSearchParams()
    if (selectedCacheType.value) {
      params.append('cache_type', selectedCacheType.value)
    }
    if (selectedCacheSize.value) {
      params.append('cache_size', selectedCacheSize.value)
    }
    
    const response = await api.get(`/my/challenges/basics/calendar?${params}`)
    calendarResult.value = response.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Erreur lors du chargement du calendrier'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    fetchCacheTypes(),
    fetchCacheSizes(),
    fetchCalendar()
  ])
})
</script>