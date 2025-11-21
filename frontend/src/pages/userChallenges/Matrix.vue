<template>
  <div class="p-4 space-y-4">
    <!-- En-tête -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">Matrix D/T Challenge</h1>
        <p class="text-gray-600">Vérification de completion des combinaisons Difficulté/Terrain</p>
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
            @change="fetchMatrix"
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
            @change="fetchMatrix"
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
      Chargement de la matrice...
    </div>
    <div v-if="error" class="text-center text-red-600 text-sm py-4 bg-red-50 rounded-lg">
      {{ error }}
    </div>

    <!-- Résultats Matrix -->
    <div v-if="matrixResult && !loading" class="space-y-4">
      <!-- Statistiques -->
      <div class="rounded-lg border bg-white p-4 shadow-sm">
        <h2 class="font-semibold mb-3">Résumé</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-green-50 p-3 rounded-lg">
            <div class="text-2xl font-bold text-green-800">
              {{ matrixResult.completed_combinations }}
            </div>
            <div class="text-sm text-green-600">
              Combinaisons complétées
            </div>
          </div>
          <div class="bg-blue-50 p-3 rounded-lg">
            <div class="text-2xl font-bold text-blue-800">
              {{ ((matrixResult.completed_combinations / 81) * 100).toFixed(1) }}%
            </div>
            <div class="text-sm text-blue-600">
              Completion (sur 81 combinaisons)
            </div>
          </div>
        </div>
      </div>

      <!-- Matrix Grid -->
      <div class="rounded-lg border bg-white p-4 shadow-sm overflow-x-auto">
        <h2 class="font-semibold mb-3">Matrice Difficulté/Terrain</h2>
        <div class="min-w-max">
          <table class="w-full border-collapse">
            <thead>
              <tr>
                <th class="border p-2 bg-gray-50 text-sm">D\T</th>
                <th 
                  v-for="terrain in terrainValues" 
                  :key="terrain"
                  class="border p-2 bg-gray-50 text-sm"
                >
                  {{ terrain }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="difficulty in difficultyValues" :key="difficulty">
                <td class="border p-2 bg-gray-50 font-medium text-sm">
                  {{ difficulty }}
                </td>
                <td 
                  v-for="terrain in terrainValues" 
                  :key="`${difficulty}-${terrain}`"
                  class="border p-2 text-center text-sm"
                  :class="getCellClass(difficulty, terrain)"
                >
                  {{ getMatrixValue(difficulty, terrain) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="mt-2 text-xs text-gray-500">
          <span class="inline-block w-4 h-4 bg-green-100 border mr-1"></span>Complété (≥1)
          <span class="inline-block w-4 h-4 bg-red-100 border mr-1 ml-3"></span>Non complété (0)
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/api/http'
import type { MatrixResult, CacheType, CacheSize } from '@/types/challenges'

const loading = ref(false)
const error = ref('')
const matrixResult = ref<MatrixResult | null>(null)
const cacheTypes = ref<CacheType[]>([])
const cacheSizes = ref<CacheSize[]>([])
const selectedCacheType = ref('')
const selectedCacheSize = ref('')

// Valeurs fixes pour la matrice D/T
const difficultyValues = ['1.0', '1.5', '2.0', '2.5', '3.0', '3.5', '4.0', '4.5', '5.0']
const terrainValues = ['1.0', '1.5', '2.0', '2.5', '3.0', '3.5', '4.0', '4.5', '5.0']

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

async function fetchCacheTypes() {
  try {
    const response = await api.get('/cache_types')
    console.log('Cache types response:', response.data)
    cacheTypes.value = response.data
  } catch (e: any) {
    console.error('Erreur chargement types:', e)
  }
}

async function fetchCacheSizes() {
  try {
    const response = await api.get('/cache_sizes')
    console.log('Cache sizes response:', response.data)
    cacheSizes.value = response.data
  } catch (e: any) {
    console.error('Erreur chargement tailles:', e)
  }
}

async function fetchMatrix() {
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
    
    const response = await api.get(`/my/challenges/basics/matrix?${params}`)
    console.log('Matrix API response:', response.data)
    matrixResult.value = response.data
    
    if (response.data?.matrix) {
      console.log('Matrix data structure:', Object.keys(response.data.matrix))
      console.log('First matrix entry:', response.data.matrix[Object.keys(response.data.matrix)[0]])
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Erreur lors du chargement de la matrice'
  } finally {
    loading.value = false
  }
}

function getMatrixValue(difficulty: string, terrain: string): number {
  if (!matrixResult.value?.matrix) {
    console.log('No matrix data available')
    return 0
  }
  
  const value = matrixResult.value.matrix[difficulty]?.[terrain] || 0
  console.log(`Matrix value for ${difficulty}/${terrain}:`, value)
  return value
}

function getCellClass(difficulty: string, terrain: string): string {
  const value = getMatrixValue(difficulty, terrain)
  if (value >= 1) {
    return 'bg-green-100 text-green-800'
  } else {
    return 'bg-red-100 text-red-800'
  }
}

onMounted(async () => {
  await Promise.all([
    fetchCacheTypes(),
    fetchCacheSizes(),
    fetchMatrix()
  ])
})
</script>