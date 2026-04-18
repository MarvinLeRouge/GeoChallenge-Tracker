import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

// ── Hoisted mocks ────────────────────────────────────────────────────────────

const mockFetchZones = vi.hoisted(() => vi.fn().mockResolvedValue([]));
const mockFetchZoneTypeStats = vi.hoisted(() =>
  vi.fn().mockResolvedValue(null),
);
const mockLoading = vi.hoisted(() => ({ value: false }));
const mockGet = vi.hoisted(() => vi.fn().mockResolvedValue({ data: {} }));

vi.mock("@/composables/useZones", () => ({
  useZones: () => ({
    loading: mockLoading,
    error: { value: null },
    fetchZones: mockFetchZones,
    fetchZoneTypeStats: mockFetchZoneTypeStats,
  }),
}));

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));

vi.mock("@heroicons/vue/24/outline", () => ({
  XCircleIcon: { template: '<svg data-testid="x-circle-icon" />' },
}));

vi.mock("leaflet", () => ({
  default: {
    geoJSON: vi.fn(() => ({
      addTo: vi.fn(),
      remove: vi.fn(),
      resetStyle: vi.fn(),
    })),
    map: vi.fn(),
  },
}));

vi.mock("@/components/map/MapBase.vue", () => ({
  default: {
    name: "MapBase",
    template: '<div data-testid="map-base" />',
    expose: ["getMap"],
  },
}));

// ── Import under test ────────────────────────────────────────────────────────

import ZoneTypeStatsMap from "@/pages/caches/ZoneTypeStatsMap.vue";
import type { ZoneTypeStatsResponse } from "@/types/zones";

// ── Factories ────────────────────────────────────────────────────────────────

const makeStats = (
  overrides: Partial<ZoneTypeStatsResponse> = {},
): ZoneTypeStatsResponse => ({
  code: "FR-84",
  name: "Auvergne-Rhône-Alpes",
  type_counts: [
    { type_code: "traditional", type_name: "Traditional", count: 10 },
    { type_code: "mystery", type_name: "Mystery", count: 0 },
    { type_code: "earth", type_name: "EarthCache", count: 2 },
  ],
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchZones.mockResolvedValue([]);
  mockFetchZoneTypeStats.mockResolvedValue(null);
  mockLoading.value = false;
});

// ── Tests: toolbar ───────────────────────────────────────────────────────────

describe("toolbar", () => {
  it("renders the level toggle buttons", () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const buttons = wrapper.findAll("button");
    const labels = buttons.map((b) => b.text());
    expect(labels).toContain("Régions");
    expect(labels).toContain("Départements");
  });

  it("highlights Régions button by default", () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const regionsBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "Régions");
    expect(regionsBtn?.classes()).toContain("bg-white");
  });
});

// ── Tests: popover ───────────────────────────────────────────────────────────

describe("popover", () => {
  it("is hidden on initial render", () => {
    const wrapper = mount(ZoneTypeStatsMap);
    expect(wrapper.find("table").exists()).toBe(false);
  });

  it("shows all type rows when popover data is set", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverStats: ZoneTypeStatsResponse | null;
      popoverVisible: boolean;
    };

    vm.popoverStats = makeStats();
    vm.popoverVisible = true;
    await flushPromises();

    const rows = wrapper.findAll("tbody tr");
    expect(rows).toHaveLength(3);
  });

  it("applies zero-count highlight class to rows with count=0", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverStats: ZoneTypeStatsResponse | null;
      popoverVisible: boolean;
    };

    vm.popoverStats = makeStats();
    vm.popoverVisible = true;
    await flushPromises();

    const rows = wrapper.findAll("tbody tr");
    const mysteryRow = rows.find((r) => r.text().includes("Mystery"));
    expect(mysteryRow?.classes()).toContain("bg-red-50");
  });

  it("does not apply zero-count class to rows with count>0", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverStats: ZoneTypeStatsResponse | null;
      popoverVisible: boolean;
    };

    vm.popoverStats = makeStats();
    vm.popoverVisible = true;
    await flushPromises();

    const rows = wrapper.findAll("tbody tr");
    const tradRow = rows.find((r) => r.text().includes("Traditional"));
    expect(tradRow?.classes()).not.toContain("bg-red-50");
  });

  it("shows XCircleIcon only on zero-count rows", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverStats: ZoneTypeStatsResponse | null;
      popoverVisible: boolean;
    };

    vm.popoverStats = makeStats();
    vm.popoverVisible = true;
    await flushPromises();

    const icons = wrapper.findAll("[data-testid='x-circle-icon']");
    // only mystery has count=0
    expect(icons).toHaveLength(1);
  });

  it("formats counts with locale thousands separator", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverStats: ZoneTypeStatsResponse | null;
      popoverVisible: boolean;
    };

    vm.popoverStats = {
      code: "FR-84",
      name: "Test",
      type_counts: [
        { type_code: "traditional", type_name: "Traditional", count: 1234 },
      ],
    };
    vm.popoverVisible = true;
    await flushPromises();

    // fr-FR uses narrow no-break space as thousands separator
    expect(wrapper.text()).toMatch(/1[\s\u202f]234/);
  });

  it("displays the zone name in the popover header", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverStats: ZoneTypeStatsResponse | null;
      popoverVisible: boolean;
    };

    vm.popoverStats = makeStats();
    vm.popoverVisible = true;
    await flushPromises();

    expect(wrapper.text()).toContain("Auvergne-Rhône-Alpes");
  });

  it("closes popover when close button is clicked", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverStats: ZoneTypeStatsResponse | null;
      popoverVisible: boolean;
      closePopover: () => void;
    };

    vm.popoverStats = makeStats();
    vm.popoverVisible = true;
    await flushPromises();

    const closeBtn = wrapper.findAll("button").find((b) => b.text() === "✕");
    await closeBtn?.trigger("click");

    expect(vm.popoverVisible).toBe(false);
  });

  it("closes popover when closePopover is called (map click outside)", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverStats: ZoneTypeStatsResponse | null;
      popoverVisible: boolean;
      closePopover: () => void;
    };

    vm.popoverStats = makeStats();
    vm.popoverVisible = true;
    await flushPromises();

    vm.closePopover();
    await flushPromises();

    expect(vm.popoverVisible).toBe(false);
    expect(vm.popoverStats).toBeNull();
  });

  it("displays the correct total count", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverStats: ZoneTypeStatsResponse | null;
      popoverVisible: boolean;
    };

    // traditional=10, mystery=0, earth=2 → total=12
    vm.popoverStats = makeStats();
    vm.popoverVisible = true;
    await flushPromises();

    expect(wrapper.text()).toContain("12");
  });
});
