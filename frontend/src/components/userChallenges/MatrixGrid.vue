<template>
  <!-- Matrix Grid -->
  <div
    class="rounded-lg border bg-white p-4 shadow-sm overflow-x-auto dark:bg-gray-800 dark:border-gray-700"
  >
    <h2 class="font-semibold mb-3">Matrice Difficulté/Terrain</h2>
    <div class="min-w-max">
      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th
              class="border p-2 bg-gray-50 text-sm dark:bg-gray-700 dark:border-gray-600"
            >
              D\T
            </th>
            <th
              v-for="terrain in terrainValues"
              :key="terrain"
              class="border p-2 bg-gray-50 text-sm dark:bg-gray-700 dark:border-gray-600"
            >
              {{ terrain }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="difficulty in difficultyValues" :key="difficulty">
            <td
              class="border p-2 bg-gray-50 font-medium text-sm dark:bg-gray-700 dark:border-gray-600"
            >
              {{ difficulty }}
            </td>
            <td
              v-for="terrain in terrainValues"
              :key="`${difficulty}-${terrain}`"
              class="border p-2 text-center text-sm dark:border-gray-600"
              :class="getCellClass(difficulty, terrain)"
            >
              {{ getMatrixValue(difficulty, terrain) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="mt-2 text-xs text-gray-500 dark:text-gray-400">
      <span
        class="inline-block w-4 h-4 bg-green-100 border mr-1 dark:bg-green-900 dark:border-gray-600"
      />Complété (≥1)
      <span
        class="inline-block w-4 h-4 bg-red-100 border mr-1 ml-3 dark:bg-red-900 dark:border-gray-600"
      />Non complété (0)
      <span v-if="matrixResult?.matrix_tours && matrixResult.matrix_tours > 0">
        <span
          class="inline-block w-4 h-4 bg-indigo-100 border mr-1 ml-3 dark:bg-indigo-900 dark:border-gray-600"
        />Next round
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MatrixResult } from "@/types/challenges";

defineProps<{
  terrainValues: number[];
  difficultyValues: number[];
  matrixResult: MatrixResult | null;
  getCellClass: (diff: number, terr: number) => string;
  getMatrixValue: (diff: number, terr: number) => number;
}>();
</script>
