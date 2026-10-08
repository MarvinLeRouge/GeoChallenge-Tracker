<template>
  <!-- Statistiques -->
  <div
    class="rounded-lg border bg-white p-4 shadow-sm dark:bg-gray-800 dark:border-gray-700"
  >
    <h2 class="font-semibold mb-3">Résumé</h2>
    <div
      v-if="matrixResult.matrix_tours && matrixResult.matrix_tours > 0"
      class="grid grid-cols-1 md:grid-cols-4 gap-4"
    >
      <div class="bg-green-50 p-3 rounded-lg dark:bg-green-950">
        <div class="flex items-center gap-2">
          <CheckCircleIcon
            class="h-6 w-6 text-green-600 shrink-0 dark:text-green-400"
            aria-hidden="true"
          />
          <div>
            <div class="text-2xl font-bold text-green-800 dark:text-green-300">
              {{ matrixResult.completed_combinations_count }}
            </div>
            <div class="text-sm text-green-700 dark:text-green-400">
              Combinaisons complétées
            </div>
          </div>
        </div>
      </div>
      <div class="bg-blue-50 p-3 rounded-lg dark:bg-blue-950">
        <div class="flex items-center gap-2">
          <Squares2X2Icon
            class="h-6 w-6 text-blue-600 shrink-0 dark:text-blue-400"
            aria-hidden="true"
          />
          <div>
            <div class="text-2xl font-bold text-blue-800 dark:text-blue-300">
              {{
                (
                  (matrixResult.completed_combinations_count /
                    MATRIX_DT_TOTAL_COMBINATIONS) *
                  100
                ).toFixed(1)
              }}%
            </div>
            <div class="text-sm text-blue-600 dark:text-blue-400">
              Completion (sur {{ MATRIX_DT_TOTAL_COMBINATIONS }}
              combinaisons)
            </div>
          </div>
        </div>
      </div>
      <div class="bg-indigo-50 p-3 rounded-lg dark:bg-indigo-950">
        <div class="flex items-center gap-2">
          <TrophyIcon
            class="h-6 w-6 text-indigo-600 shrink-0 dark:text-indigo-400"
            aria-hidden="true"
          />
          <div>
            <div
              class="text-2xl font-bold text-indigo-800 dark:text-indigo-300"
            >
              {{ matrixResult.matrix_tours }}
            </div>
            <div class="text-sm text-indigo-600 dark:text-indigo-400">
              {{
                matrixResult.matrix_tours > 1
                  ? "Tours de matrice"
                  : "Tour de matrice"
              }}
            </div>
          </div>
        </div>
      </div>
      <div class="bg-purple-50 p-3 rounded-lg dark:bg-purple-950">
        <div class="flex items-center gap-2">
          <ArrowPathIcon
            class="h-6 w-6 text-purple-600 shrink-0 dark:text-purple-400"
            aria-hidden="true"
          />
          <div>
            <div
              class="text-2xl font-bold text-purple-800 dark:text-purple-300"
            >
              {{ (matrixResult.next_round_completion_rate * 100).toFixed(1) }}%
            </div>
            <div class="text-sm text-purple-600 dark:text-purple-400">
              Next round : {{ matrixResult.next_round_completed_count }}/{{
                MATRIX_DT_TOTAL_COMBINATIONS
              }}
              combinaisons
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="bg-green-50 p-3 rounded-lg dark:bg-green-950">
        <div class="flex items-center gap-2">
          <CheckCircleIcon
            class="h-6 w-6 text-green-600 shrink-0 dark:text-green-400"
            aria-hidden="true"
          />
          <div>
            <div class="text-2xl font-bold text-green-800 dark:text-green-300">
              {{ matrixResult.completed_combinations_count }}
            </div>
            <div class="text-sm text-green-700 dark:text-green-400">
              Combinaisons complétées
            </div>
          </div>
        </div>
      </div>
      <div class="bg-blue-50 p-3 rounded-lg dark:bg-blue-950">
        <div class="flex items-center gap-2">
          <Squares2X2Icon
            class="h-6 w-6 text-blue-600 shrink-0 dark:text-blue-400"
            aria-hidden="true"
          />
          <div>
            <div class="text-2xl font-bold text-blue-800 dark:text-blue-300">
              {{
                (
                  (matrixResult.completed_combinations_count /
                    MATRIX_DT_TOTAL_COMBINATIONS) *
                  100
                ).toFixed(1)
              }}%
            </div>
            <div class="text-sm text-blue-600 dark:text-blue-400">
              Completion (sur {{ MATRIX_DT_TOTAL_COMBINATIONS }}
              combinaisons)
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MatrixResult } from "@/types/challenges";
import { MATRIX_DT_TOTAL_COMBINATIONS } from "@/constants/matrix";
import {
  CheckCircleIcon,
  Squares2X2Icon,
  TrophyIcon,
  ArrowPathIcon,
} from "@heroicons/vue/24/outline";

defineProps<{
  matrixResult: MatrixResult;
}>();
</script>
