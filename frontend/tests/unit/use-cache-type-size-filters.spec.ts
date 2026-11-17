import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref } from "vue";

const mockGet = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));
vi.mock("vue-sonner", () => ({ toast: { error: mockToastError } }));

import { useCacheTypeSizeFilters } from "@/composables/useCacheTypeSizeFilters";

beforeEach(() => vi.resetAllMocks());

describe("useCacheTypeSizeFilters", () => {
  it("sorts types alphabetically and sizes in logical order", async () => {
    mockGet
      .mockResolvedValueOnce({ data: [{ name: "Mystery" }, { name: "Earth" }] })
      .mockResolvedValueOnce({
        data: [{ name: "Large" }, { name: "Micro" }, { name: "Regular" }],
      });
    const f = useCacheTypeSizeFilters(ref(""));

    await f.fetchCacheTypes();
    await f.fetchCacheSizes();

    expect(mockGet.mock.calls.map((c) => c[0])).toEqual([
      "/cache_types",
      "/cache_sizes",
    ]);
    expect(f.sortedCacheTypes.value.map((t) => t.name)).toEqual([
      "Earth",
      "Mystery",
    ]);
    expect(f.sortedCacheSizes.value.map((s) => s.name)).toEqual([
      "Micro",
      "Regular",
      "Large",
    ]);
  });

  it.each([
    ["fetchCacheTypes", "Erreur chargement types"],
    ["fetchCacheSizes", "Erreur chargement tailles"],
  ] as const)(
    "%s sets the error and toasts an Error message",
    async (method, label) => {
      mockGet.mockRejectedValueOnce(new Error("boom"));
      const error = ref("");

      await useCacheTypeSizeFilters(error)[method]();

      expect(error.value).toBe(`${label}: boom`);
      expect(mockToastError).toHaveBeenCalledWith(label, {
        description: "boom",
      });
    },
  );

  it.each(["fetchCacheTypes", "fetchCacheSizes"] as const)(
    "%s stringifies a non-Error rejection",
    async (method) => {
      mockGet.mockRejectedValueOnce("offline");
      const error = ref("");

      await useCacheTypeSizeFilters(error)[method]();

      expect(error.value).toMatch(/: offline$/);
    },
  );
});
