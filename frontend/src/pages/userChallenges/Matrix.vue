<template>
  <div class="p-4 space-y-4">
    <!-- En-tête -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">Matrix D/T Challenge</h1>
        <p class="text-gray-600 dark:text-gray-400">
          Vérification de completion des combinaisons Difficulté/Terrain
        </p>
      </div>
    </div>

    <!-- Filtres -->
    <CacheTypeSizeFilters
      v-model:selected-cache-type="selectedCacheType"
      v-model:selected-cache-size="selectedCacheSize"
      :sorted-cache-types="sortedCacheTypes"
      :sorted-cache-sizes="sortedCacheSizes"
      @change="fetchMatrix"
    />

    <!-- Loading/Error -->
    <div v-if="loading" class="py-8">
      <LoadingIndicator label="Chargement de la matrice…" />
    </div>
    <div
      v-if="error"
      class="text-center text-red-600 text-sm py-4 bg-red-50 rounded-lg dark:text-red-400 dark:bg-red-950"
    >
      {{ error }}
    </div>

    <!-- Résultats Matrix -->
    <div v-if="matrixResult && !loading" class="space-y-4">
      <MatrixSummaryStats :matrix-result="matrixResult" />

      <MatrixGrid
        :terrain-values="terrainValues"
        :difficulty-values="difficultyValues"
        :matrix-result="matrixResult"
        :get-cell-class="getCellClass"
        :get-matrix-value="getMatrixValue"
      />

      <!-- Combinaisons manquantes pour le prochain tour -->
      <div
        v-if="nextRoundTargets.length > 0"
        class="rounded-lg border bg-white p-4 shadow-xs dark:bg-gray-800 dark:border-gray-700"
      >
        <h2 class="font-semibold mb-3">
          Combinaisons manquantes pour le tour
          {{ (matrixResult?.matrix_tours ?? 0) + 1 }}
        </h2>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="combo in nextRoundTargets"
            :key="`${combo.difficulty}-${combo.terrain}`"
            class="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-100 px-3 py-1 text-sm font-medium text-indigo-800 dark:border-indigo-500 dark:bg-indigo-950 dark:text-indigo-200"
          >
            D{{ combo.difficulty }} / T{{ combo.terrain }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import api from "@/api/http";
import type { MatrixResult } from "@/types/challenges";
import { useMatrixData } from "@/composables/useMatrixData";
import { useCacheTypeSizeFilters } from "@/composables/useCacheTypeSizeFilters";
import { toast } from "vue-sonner";
import LoadingIndicator from "@/components/ui/LoadingIndicator.vue";
import MatrixSummaryStats from "@/components/userChallenges/MatrixSummaryStats.vue";
import MatrixGrid from "@/components/userChallenges/MatrixGrid.vue";
import CacheTypeSizeFilters from "@/components/userChallenges/CacheTypeSizeFilters.vue";

const loading = ref(false);
const error = ref("");
const matrixResult = ref<MatrixResult | null>(null);

// Use the shared composable for cache type/size filters
const {
  selectedCacheType,
  selectedCacheSize,
  sortedCacheTypes,
  sortedCacheSizes,
  fetchCacheTypes,
  fetchCacheSizes,
} = useCacheTypeSizeFilters(error);

// Use the new composable for matrix data processing
const { matrixData, terrainValues, difficultyValues } =
  useMatrixData(matrixResult);

// Cells stuck at the current matrix_tours value: the ones needed to reach the next round
const nextRoundTargets = computed(() => {
  const tours = matrixResult.value?.matrix_tours ?? 0;
  if (tours === 0) return [];

  return matrixData.value.rows.flatMap((row) =>
    row.cells
      .filter((cell) => cell.count === tours)
      .map((cell) => ({ difficulty: cell.difficulty, terrain: cell.terrain })),
  );
});

async function fetchMatrix() {
  loading.value = true;
  error.value = "";

  try {
    const params = new URLSearchParams();
    if (selectedCacheType.value) {
      params.append("cache_type", selectedCacheType.value);
    }
    if (selectedCacheSize.value) {
      params.append("cache_size", selectedCacheSize.value);
    }

    const response = await api.get(`/my/challenges/basics/matrix?${params}`);
    matrixResult.value = response.data;
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })
      ?.response?.data?.detail;
    const msg = e instanceof Error ? e.message : String(e);
    error.value = detail || msg || "Erreur lors du chargement de la matrice";
    toast.error("Erreur chargement matrice", { description: error.value });
  } finally {
    loading.value = false;
  }
}

function getMatrixValue(diff: number, terr: number): number {
  // Find the combination in the processed matrix data
  const row = matrixData.value.rows.find((r) => r.difficulty === diff);
  if (!row) return 0;

  const cell = row.cells.find((c) => c.terrain === terr);
  return cell ? cell.count : 0;
}

function getCellClass(diff: number, terr: number): string {
  // Find the combination in the processed matrix data
  const row = matrixData.value.rows.find((r) => r.difficulty === diff);
  if (!row) return "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300";

  const cell = row.cells.find((c) => c.terrain === terr);
  if (!cell) return "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300";

  // Check if this cell is needed for the next round
  if (
    matrixResult.value &&
    matrixResult.value.matrix_tours > 0 &&
    cell.count === matrixResult.value.matrix_tours
  ) {
    // Color for next round target cells
    return "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200";
  }

  return cell.isCompleted
    ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300"
    : "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300";
}

onMounted(async () => {
  await Promise.all([fetchCacheTypes(), fetchCacheSizes(), fetchMatrix()]);
});
</script>
