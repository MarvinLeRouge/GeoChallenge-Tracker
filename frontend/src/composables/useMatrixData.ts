// src/composables/useMatrixData.ts
import { ref, computed, type Ref } from 'vue';
import type { MatrixResult } from '@/types/challenges';

export interface MatrixCell {
  difficulty: number;
  terrain: number;
  count: number;
  isCompleted: boolean;
}

export interface MatrixRow {
  difficulty: number;
  cells: MatrixCell[];
}

export interface MatrixDisplayData {
  rows: MatrixRow[];
  completionRate: number;
  completedCombinations: number;
  totalCombinations: number;
}

export function useMatrixData(matrixResult: Ref<MatrixResult | null>) {
  // Fixed values for the matrix D/T
  const difficultyValues = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0];
  const terrainValues = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0];

  const matrixData = computed(() => {
    if (!matrixResult.value) {
      return {
        rows: [],
        completionRate: 0,
        completedCombinations: 0,
        totalCombinations: 0
      };
    }

    const rows: MatrixRow[] = [];

    for (const difficulty of difficultyValues) {
      const cells: MatrixCell[] = [];

      for (const terrain of terrainValues) {
        // Check if this combination is in missing_combinations
        const isMissing = matrixResult.value.missing_combinations.some(
          combo => combo.difficulty === difficulty && combo.terrain === terrain
        );

        if (isMissing) {
          // Combination is missing (not completed)
          cells.push({
            difficulty,
            terrain,
            count: 0,
            isCompleted: false
          });
        } else {
          // Find the combination in completed_combinations_details
          const combination = matrixResult.value.completed_combinations_details.find(
            combo => combo.difficulty === difficulty && combo.terrain === terrain
          );

          const count = combination ? combination.count : 0;
          const isCompleted = count >= 1;

          cells.push({
            difficulty,
            terrain,
            count,
            isCompleted
          });
        }
      }

      rows.push({
        difficulty,
        cells
      });
    }

    return {
      rows,
      completionRate: (matrixResult.value.completed_combinations / 81) * 100,
      completedCombinations: matrixResult.value.completed_combinations,
      totalCombinations: 81
    };
  });

  return {
    matrixData,
    difficultyValues,
    terrainValues
  };
}