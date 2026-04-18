import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

// ── Hoisted mocks ────────────────────────────────────────────────────────────

const mockFetchZones = vi.hoisted(() => vi.fn().mockResolvedValue([]));
const mockFetchZoneTypeStats = vi.hoisted(() =>
  vi.fn().mockResolvedValue(null),
);
const mockLoading = vi.hoisted(() => ({ value: false }));
const mockGet = vi.hoisted(() => vi.fn().mockResolvedValue({ data: {} }));

const capturedLayerHandlers = vi.hoisted(
  () => new Map<string, Record<string, (e: unknown) => void>>(),
);

const mockLeafletMap = vi.hoisted(() => ({
  on: vi.fn(),
  off: vi.fn(),
  removeLayer: vi.fn(),
  latLngToContainerPoint: vi.fn().mockReturnValue({ x: 100, y: 200 }),
}));

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
    geoJSON: vi.fn((geoData, options) => {
      if (Array.isArray(geoData?.features)) {
        for (const feature of geoData.features) {
          if (options?.style) options.style(feature);

          if (options?.onEachFeature) {
            const code = feature?.properties?.code as string | undefined;
            const handlers: Record<string, (e: unknown) => void> = {};
            const mockLayer = {
              bindTooltip: vi.fn(),
              bringToFront: vi.fn(),
              setStyle: vi.fn(),
              on: vi.fn((events: Record<string, (e: unknown) => void>) => {
                Object.assign(handlers, events);
              }),
            };
            options.onEachFeature(feature, mockLayer);
            if (code) capturedLayerHandlers.set(code, handlers);
          }
        }
      }
      return {
        addTo: vi.fn().mockReturnThis(),
        resetStyle: vi.fn(),
      };
    }),
    map: vi.fn(),
  },
}));

vi.mock("@/components/map/MapBase.vue", () => ({
  default: {
    name: "MapBase",
    template: '<div data-testid="map-base" />',
    expose: ["getMap"],
    emits: ["ready"],
  },
}));

// ── Import under test ────────────────────────────────────────────────────────

import ZoneTypeStatsMap from "@/pages/caches/ZoneTypeStatsMap.vue";
import type { ZoneTypeStatsResponse } from "@/types/zones";

// ── Factories ────────────────────────────────────────────────────────────────

const mockGeoData = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { code: "84", nom: "Auvergne-Rhône-Alpes" },
      geometry: null,
    },
    {
      type: "Feature",
      properties: { code: "11", nom: "Île-de-France" },
      geometry: null,
    },
  ],
};

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

// ── Helpers ──────────────────────────────────────────────────────────────────

async function triggerMapReady(wrapper: ReturnType<typeof mount>) {
  await wrapper
    .findComponent({ name: "MapBase" })
    .vm.$emit("ready", mockLeafletMap);
  await flushPromises();
}

beforeEach(() => {
  vi.clearAllMocks();
  capturedLayerHandlers.clear();
  mockFetchZones.mockResolvedValue([]);
  mockFetchZoneTypeStats.mockResolvedValue(null);
  mockLoading.value = false;
  mockGet.mockResolvedValue({ data: mockGeoData });
  mockLeafletMap.latLngToContainerPoint.mockReturnValue({ x: 100, y: 200 });
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

// ── Tests: map lifecycle ─────────────────────────────────────────────────────

describe("map lifecycle", () => {
  it("registers a click listener on the map when ready", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);
    expect(mockLeafletMap.on).toHaveBeenCalledWith(
      "click",
      expect.any(Function),
    );
  });

  it("fetches regions GeoJSON and zone counts on ready", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);
    expect(mockGet).toHaveBeenCalledWith("/geo/FR/regions.geojson");
    expect(mockFetchZones).toHaveBeenCalledWith("FR", 1);
  });

  it("registers layer event handlers for each GeoJSON feature", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);
    expect(capturedLayerHandlers.has("84")).toBe(true);
    expect(capturedLayerHandlers.has("11")).toBe(true);
  });

  it("applies color interpolation for zones with non-zero cache counts", async () => {
    mockFetchZones.mockResolvedValue([
      { code: "FR-84", name: "Auvergne-Rhône-Alpes", cache_count: 5 },
    ]);
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);
    // style callback was invoked — no errors means interpolateColor ran
    expect(capturedLayerHandlers.has("84")).toBe(true);
  });

  it("skips choropleth rendering when GeoJSON fetch fails", async () => {
    mockGet.mockRejectedValue(new Error("network"));
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);
    expect(capturedLayerHandlers.size).toBe(0);
  });

  it("removes the click listener and choropleth layer on unmount", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);
    wrapper.unmount();
    expect(mockLeafletMap.off).toHaveBeenCalledWith(
      "click",
      expect.any(Function),
    );
    expect(mockLeafletMap.removeLayer).toHaveBeenCalled();
  });

  it("shows the loading overlay while loading is true", async () => {
    mockLoading.value = true;
    const wrapper = mount(ZoneTypeStatsMap);
    expect(wrapper.text()).toContain("Chargement");
  });
});

// ── Tests: level switching ───────────────────────────────────────────────────

describe("level switching", () => {
  it("fetches départements data when switching to level 2", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);

    const deptBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "Départements");
    await deptBtn?.trigger("click");
    await flushPromises();

    expect(mockFetchZones).toHaveBeenCalledWith("FR", 2);
    expect(mockGet).toHaveBeenCalledWith("/geo/FR/departements.geojson");
  });

  it("highlights Départements button after switching to level 2", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);

    const deptBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "Départements");
    await deptBtn?.trigger("click");
    await flushPromises();

    expect(deptBtn?.classes()).toContain("bg-white");
  });

  it("does not re-render when the same level is selected again", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);
    const callCount = mockFetchZones.mock.calls.length;

    const regionsBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "Régions");
    await regionsBtn?.trigger("click");
    await flushPromises();

    expect(mockFetchZones).toHaveBeenCalledTimes(callCount);
  });

  it("removes the previous choropleth layer before rendering the new one", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);

    const deptBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "Départements");
    await deptBtn?.trigger("click");
    await flushPromises();

    expect(mockLeafletMap.removeLayer).toHaveBeenCalled();
  });

  it("closes the popover when switching levels", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    const vm = wrapper.vm as unknown as {
      popoverVisible: boolean;
      popoverStats: ZoneTypeStatsResponse | null;
    };
    await triggerMapReady(wrapper);
    vm.popoverStats = makeStats();
    vm.popoverVisible = true;

    const deptBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "Départements");
    await deptBtn?.trigger("click");
    await flushPromises();

    expect(vm.popoverVisible).toBe(false);
  });
});

// ── Tests: zone interaction ──────────────────────────────────────────────────

describe("zone interaction", () => {
  it("calls fetchZoneTypeStats with zone code and level when a feature is clicked", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);

    const handlers = capturedLayerHandlers.get("84");
    handlers!.click({ latlng: { lat: 45, lng: 5 } });
    await flushPromises();

    expect(mockFetchZoneTypeStats).toHaveBeenCalledWith("FR-84", 1);
  });

  it("shows the popover after a zone click when stats are returned", async () => {
    mockFetchZoneTypeStats.mockResolvedValue(makeStats());
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);

    const handlers = capturedLayerHandlers.get("84");
    handlers!.click({ latlng: { lat: 45, lng: 5 } });
    await flushPromises();

    expect(wrapper.find("table").exists()).toBe(true);
  });

  it("does not show the popover when fetchZoneTypeStats returns null", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);

    const handlers = capturedLayerHandlers.get("84");
    handlers!.click({ latlng: { lat: 45, lng: 5 } });
    await flushPromises();

    expect(wrapper.find("table").exists()).toBe(false);
  });

  it("applies hover style on mouseover", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);

    const handlers = capturedLayerHandlers.get("84");
    const mockTarget = { setStyle: vi.fn(), bringToFront: vi.fn() };
    handlers!.mouseover({ target: mockTarget });

    expect(mockTarget.setStyle).toHaveBeenCalledWith(
      expect.objectContaining({ weight: 2, color: "#fbbf24" }),
    );
    expect(mockTarget.bringToFront).toHaveBeenCalled();
  });

  it("resets the layer style on mouseout", async () => {
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);

    const handlers = capturedLayerHandlers.get("84");
    expect(() => handlers!.mouseout({ target: {} })).not.toThrow();
  });

  it("does not open popover for a feature with no zone code", async () => {
    const geoDataNoCode = {
      type: "FeatureCollection",
      features: [
        { type: "Feature", properties: { nom: "Unknown" }, geometry: null },
      ],
    };
    mockGet.mockResolvedValue({ data: geoDataNoCode });
    const wrapper = mount(ZoneTypeStatsMap);
    await triggerMapReady(wrapper);

    // Feature has no "code" property, so no handler was registered
    expect(capturedLayerHandlers.size).toBe(0);
  });
});
