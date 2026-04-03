import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { nextTick } from "vue";

const mockGet = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());
const mockToastInfo = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));
vi.mock("vue-sonner", () => ({
  toast: { error: mockToastError, info: mockToastInfo },
}));

import Calendar from "@/pages/userChallenges/Calendar.vue";

const makeCalendarResult = (overrides = {}) => ({
  total_days_365: 365,
  completed_days_365: 200,
  completion_rate_365: 54.8,
  total_days_366: 366,
  completed_days_366: 200,
  completion_rate_366: 54.6,
  missing_days: ["01-05", "02-14"],
  missing_days_by_month: { "1": ["01-05"] },
  completed_days: [{ day: "2023-01-01", count: 1 }],
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
    return Promise.resolve({ data: makeCalendarResult() });
  });
});

describe("Calendar", () => {
  it("calls cache_types, cache_sizes and calendar APIs on mount", async () => {
    mount(Calendar);
    await flushPromises();

    expect(mockGet).toHaveBeenCalledWith("/cache_types");
    expect(mockGet).toHaveBeenCalledWith("/cache_sizes");
    expect(mockGet).toHaveBeenCalledWith(
      expect.stringContaining("/my/challenges/basics/calendar"),
    );
  });

  it("shows loading state during fetch", async () => {
    let resolve: (v: unknown) => void;
    mockGet.mockImplementation(() => new Promise((r) => (resolve = r)));
    const wrapper = mount(Calendar);
    await nextTick(); // wait for loading.value = true to propagate to DOM
    expect(wrapper.text()).toContain("Chargement du calendrier");
    resolve!({ data: makeCalendarResult() });
  });

  it("renders calendar stats after successful fetch", async () => {
    const wrapper = mount(Calendar);
    await flushPromises();
    // Error panel (bg-red-50) must not appear; summary section must appear
    expect(wrapper.find(".bg-red-50").exists()).toBe(false);
    expect(wrapper.text()).toContain("Résumé");
  });

  it("shows error message when calendar fetch fails", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("calendar"))
        return Promise.reject(new Error("Server error"));
      if (url === "/cache_types") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
    const wrapper = mount(Calendar);
    await flushPromises();
    expect(wrapper.text()).toContain("Server error");
    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur chargement calendrier",
      expect.any(Object),
    );
  });

  it("shows error toast when cache_types fetch fails", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/cache_types")
        return Promise.reject(new Error("types fail"));
      if (url === "/cache_sizes") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: makeCalendarResult() });
    });
    mount(Calendar);
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
      return Promise.resolve({ data: makeCalendarResult() });
    });
    mount(Calendar);
    await flushPromises();
    expect(mockToastError).toHaveBeenCalledWith(
      "Erreur chargement tailles",
      expect.any(Object),
    );
  });

  it("renders sorted cache types in the select", async () => {
    const wrapper = mount(Calendar);
    await flushPromises();
    const options = wrapper.findAll("select")[0].findAll("option");
    const texts = options.map((o) => o.text());
    // Sorted alphabetically: Mystery before Traditional
    const mysteryIdx = texts.findIndex((t) => t.includes("Mystery"));
    const tradIdx = texts.findIndex((t) => t.includes("Traditional"));
    expect(mysteryIdx).toBeLessThan(tradIdx);
  });

  it("includes cache_type param when a type is selected", async () => {
    const wrapper = mount(Calendar);
    await flushPromises();
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: makeCalendarResult() });

    await wrapper.findAll("select")[0].setValue("T");
    await flushPromises();

    expect(mockGet).toHaveBeenCalledWith(
      expect.stringContaining("cache_type=T"),
    );
  });

  it("includes cache_size param when a size is selected", async () => {
    const wrapper = mount(Calendar);
    await flushPromises();
    vi.clearAllMocks();
    mockGet.mockResolvedValue({ data: makeCalendarResult() });

    await wrapper.findAll("select")[1].setValue("S");
    await flushPromises();

    expect(mockGet).toHaveBeenCalledWith(
      expect.stringContaining("cache_size=S"),
    );
  });

  it("shows api error detail when available", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("calendar"))
        return Promise.reject({
          response: { data: { detail: "Custom detail error" } },
        });
      if (url === "/cache_types") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
    const wrapper = mount(Calendar);
    await flushPromises();
    expect(wrapper.text()).toContain("Custom detail error");
  });
});
