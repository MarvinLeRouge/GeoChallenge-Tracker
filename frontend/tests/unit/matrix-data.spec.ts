import { describe, it, expect } from "vitest";
import { ref } from "vue";
import { useMatrixData } from "@/composables/useMatrixData";
import type { MatrixResult } from "@/types/challenges";

const makeMatrixResult = (
  overrides: Partial<MatrixResult> = {},
): MatrixResult => ({
  missing_combinations: [],
  completed_combinations_details: [],
  completed_combinations_count: 0,
  ...overrides,
});

describe("matrixData", () => {
  it("returns empty structure when matrixResult is null", () => {
    const { matrixData } = useMatrixData(ref(null));
    expect(matrixData.value.rows).toEqual([]);
    expect(matrixData.value.completionRate).toBe(0);
    expect(matrixData.value.completedCombinations).toBe(0);
    expect(matrixData.value.totalCombinations).toBe(0);
  });

  it("builds a 9×9 grid of rows and cells", () => {
    const { matrixData } = useMatrixData(ref(makeMatrixResult()));
    expect(matrixData.value.rows).toHaveLength(9);
    matrixData.value.rows.forEach((row) => {
      expect(row.cells).toHaveLength(9);
    });
  });

  it("marks missing combinations as not completed", () => {
    const result = makeMatrixResult({
      missing_combinations: [{ difficulty: 1.0, terrain: 1.0 }],
    });
    const { matrixData } = useMatrixData(ref(result));
    const cell = matrixData.value.rows[0].cells[0];
    expect(cell.isCompleted).toBe(false);
    expect(cell.count).toBe(0);
  });

  it("marks found combinations as completed with correct count", () => {
    const result = makeMatrixResult({
      completed_combinations_details: [
        { difficulty: 1.0, terrain: 1.5, count: 3 },
      ],
    });
    const { matrixData } = useMatrixData(ref(result));
    const cell = matrixData.value.rows[0].cells[1]; // difficulty=1.0, terrain=1.5
    expect(cell.isCompleted).toBe(true);
    expect(cell.count).toBe(3);
  });

  it("marks a combination with count=0 as not completed even if not missing", () => {
    const result = makeMatrixResult({
      completed_combinations_details: [
        { difficulty: 2.0, terrain: 2.0, count: 0 },
      ],
    });
    const { matrixData } = useMatrixData(ref(result));
    const row = matrixData.value.rows.find((r) => r.difficulty === 2.0)!;
    const cell = row.cells.find((c) => c.terrain === 2.0)!;
    expect(cell.isCompleted).toBe(false);
  });

  it("computes completionRate from completed_combinations_count over 81", () => {
    const result = makeMatrixResult({ completed_combinations_count: 81 });
    const { matrixData } = useMatrixData(ref(result));
    expect(matrixData.value.completionRate).toBeCloseTo(100);
  });

  it("exposes totalCombinations as 81", () => {
    const { matrixData } = useMatrixData(ref(makeMatrixResult()));
    expect(matrixData.value.totalCombinations).toBe(81);
  });

  it("reacts to matrixResult changes", () => {
    const matrixResult = ref<MatrixResult | null>(null);
    const { matrixData } = useMatrixData(matrixResult);
    expect(matrixData.value.rows).toHaveLength(0);
    matrixResult.value = makeMatrixResult({ completed_combinations_count: 10 });
    expect(matrixData.value.rows).toHaveLength(9);
    expect(matrixData.value.completedCombinations).toBe(10);
  });
});

describe("difficultyValues / terrainValues", () => {
  it("exposes 9 difficulty values from 1.0 to 5.0", () => {
    const { difficultyValues } = useMatrixData(ref(null));
    expect(difficultyValues).toHaveLength(9);
    expect(difficultyValues[0]).toBe(1.0);
    expect(difficultyValues[8]).toBe(5.0);
  });

  it("exposes 9 terrain values from 1.0 to 5.0", () => {
    const { terrainValues } = useMatrixData(ref(null));
    expect(terrainValues).toHaveLength(9);
    expect(terrainValues[0]).toBe(1.0);
    expect(terrainValues[8]).toBe(5.0);
  });
});
