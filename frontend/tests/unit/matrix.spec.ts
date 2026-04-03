import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { nextTick } from "vue";

const mockGet = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));
vi.mock("vue-sonner", () => ({
  toast: { error: mockToastError },
}));

import Matrix from "@/pages/userChallenges/Matrix.vue";

const makeMatrixResult = (overrides = {}) => ({
  total_combinations: 81,
  completed_combinations_count: 40,
  completion_rate: 0.494,
  matrix_tours: 0,
  next_round_completed_count: 0,
  next_round_completion_rate: 0,
  missing_combinations: [{ difficulty: 1.0, terrain: 1.0 }],
  missing_combinations_by_difficulty: { "1.0": [{ terrain: 1.0 }] },
  completed_combinations_details: [{ difficulty: 1.5, terrain: 1.5, count: 2 }],
  ...overrides,
});

const makeCacheTypes = () => [
  { _id: "1", name: "Traditional", code: "T" },
  { _id: "2", name: "Mystery", code: "M" },
];

const makeCacheSizes = () => [
  { _id: "1", name: "Small", code: "S" },
  { _id: "2", name: "Regular", code: "R" },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockGet.mockImplementation((url: string) => {
    if (url === "/cache_types")
      return Promise.resolve({ data: makeCacheTypes() });
    if (url === "/cache_sizes")
      return Promise.resolve({ data: makeCacheSizes() });
    return Promise.resolve({ data: makeMatrixResult() });
  });
});

describe("Matrix", () => {
  it("calls cache_types, cache_sizes and matrix APIs on mount", async () => {
    mount(Matrix);
    await flushPromises();

    expect(mockGet).toHaveBeenCalledWith("/cache_types");
    expect(mockGet).toHaveBeenCalledWith("/cache_sizes");
    expect(mockGet).toHaveBeenCalledWith(
      expect.stringContaining("/my/challenges/basics/matrix"),
    );
  });

  it("shows loading state during fetch", async () => {
    let resolve: (v: unknown) => void;
    mockGet.mockImplementation(() => new Promise((r) => (resolve = r)));
    const wrapper = mount(Matrix);
    await nextTick();
    expect(wrapper.text()).toContain("Chargement de la matrice");
    resolve!({ data: makeMatrixResult() });
  });

  it("renders matrix summary after successful fetch", async () => {
    const wrapper = mount(Matrix);
    await flushPromises();
    expect(wrapper.find(".bg-red-50").exists()).toBe(false);
    expect(wrapper.text()).toContain("Résumé");
  });

  it("shows error message when matrix fetch fails", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("matrix"))
        return Promise.reject(new Error("Server error"));
      if (url === "/cache_types") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
    const wrapper = mount(Matrix);
    await flushPromises();
    expect(wrapper.text()).toContain("Server error");
    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur chargement matrice",
      expect.any(Object),
    );
  });

  it("shows error toast when cache_types fetch fails", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/cache_types")
        return Promise.reject(new Error("types fail"));
      if (url === "/cache_sizes") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: makeMatrixResult() });
    });
    mount(Matrix);
    await flushPromises();
    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur chargement types",
      expect.any(Object),
    );
  });

  it("shows error toast when cache_sizes fetch fails", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/cache_types") return Promise.resolve({ data: [] });
      if (url === "/cache_sizes")
        return Promise.reject(new Error("sizes fail"));
      return Promise.resolve({ data: makeMatrixResult() });
    });
    mount(Matrix);
    await flushPromises();
    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur chargement tailles",
      expect.any(Object),
    );
  });

  it("renders sorted cache types in the select", async () => {
    const wrapper = mount(Matrix);
    await flushPromises();
    const options = wrapper.findAll("select")[0].findAll("option");
    const texts = options.map((o) => o.text());
    const mysteryIdx = texts.findIndex((t) => t.includes("Mystery"));
    const tradIdx = texts.findIndex((t) => t.includes("Traditional"));
    expect(mysteryIdx).toBeLessThan(tradIdx);
  });

  it("includes cache_type param when a type is selected", async () => {
    const wrapper = mount(Matrix);
    await flushPromises();
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: makeMatrixResult() });

    await wrapper.findAll("select")[0].setValue("T");
    await flushPromises();

    expect(mockGet).toHaveBeenCalledWith(
      expect.stringContaining("cache_type=T"),
    );
  });

  it("includes cache_size param when a size is selected", async () => {
    const wrapper = mount(Matrix);
    await flushPromises();
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: makeMatrixResult() });

    await wrapper.findAll("select")[1].setValue("S");
    await flushPromises();

    expect(mockGet).toHaveBeenCalledWith(
      expect.stringContaining("cache_size=S"),
    );
  });

  it("shows api error detail when available", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("matrix"))
        return Promise.reject({
          response: { data: { detail: "Custom matrix error" } },
        });
      if (url === "/cache_types") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
    const wrapper = mount(Matrix);
    await flushPromises();
    expect(wrapper.text()).toContain("Custom matrix error");
  });

  it("renders matrix grid when result is available", async () => {
    const wrapper = mount(Matrix);
    await flushPromises();
    // Matrix grid has D/T headers
    expect(wrapper.text()).toContain("D\\T");
  });

  it("renders indigo cell when cell count equals matrix_tours (next round target)", async () => {
    const result = makeMatrixResult({
      matrix_tours: 1,
      next_round_completed_count: 0,
      next_round_completion_rate: 0,
      missing_combinations: [],
      completed_combinations_details: [
        { difficulty: 1.5, terrain: 1.5, count: 1 },
      ],
    });
    mockGet.mockImplementation((url: string) => {
      if (url === "/cache_types") return Promise.resolve({ data: [] });
      if (url === "/cache_sizes") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: result });
    });
    const wrapper = mount(Matrix);
    await flushPromises();
    expect(wrapper.html()).toContain("bg-indigo-100");
  });
});
