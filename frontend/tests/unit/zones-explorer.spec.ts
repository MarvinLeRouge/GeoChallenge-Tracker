import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const mockFetchCountries = vi.hoisted(() => vi.fn().mockResolvedValue([]));
const mockFetchZones = vi.hoisted(() => vi.fn().mockResolvedValue([]));
const mockFetchZoneDetail = vi.hoisted(() => vi.fn().mockResolvedValue(null));
// Must carry Vue's internal ref marker (not a plain { value: false }
// object): the component's `v-if="loading"` relies on <script setup>'s
// template auto-unwrapping, which only unwraps values Vue recognizes as
// refs (checked via isRef, i.e. `__v_isRef === true`). A plain object
// would stay truthy in the template regardless of its `.value`.
const mockLoading = vi.hoisted(() => ({ value: false, __v_isRef: true }));
// Path-keyed (not FIFO-queue-based): Task 8 adds a second, independent
// api.get() caller (loadCacheTypes, for /cache_types) that fires in
// parallel with the World view's own calls, so a plain mockResolvedValueOnce
// queue would silently hand the wrong response to the wrong caller depending
// on call order. Each test configures responses via mockGetResponses.set(path, ...).
const mockGetResponses = vi.hoisted(() => new Map<string, unknown>());
const mockGet = vi.hoisted(() =>
  vi.fn((path: string) => {
    if (mockGetResponses.has(path)) {
      const value = mockGetResponses.get(path);
      if (value instanceof Error) return Promise.reject(value);
      return Promise.resolve({ data: value });
    }
    return Promise.resolve({ data: {} });
  }),
);
const mockLeafletMap = vi.hoisted(() => ({
  removeLayer: vi.fn(),
  fitBounds: vi.fn(),
  latLngToContainerPoint: vi.fn().mockReturnValue({ x: 100, y: 100 }),
}));

vi.mock("@/composables/useZones", () => ({
  useZones: () => ({
    loading: mockLoading,
    error: { value: null },
    fetchCountries: mockFetchCountries,
    fetchZones: mockFetchZones,
    fetchZoneDetail: mockFetchZoneDetail,
  }),
}));

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));

// MapBase emits "ready" on mount (mirroring the real component, which emits
// once Leaflet's map instance exists) so that ZonesExplorer's onMapReady
// handler - and everything chained off it (renderChoropleth, etc.) - runs
// whenever the v-else branch (Country/Region view) mounts, exactly as it
// would in the browser.
vi.mock("@/components/map/MapBase.vue", () => ({
  default: {
    name: "MapBase",
    template: '<div data-testid="map-base" />',
    expose: ["getMap"],
    emits: ["ready"],
    mounted() {
      this.$emit("ready", mockLeafletMap);
    },
  },
}));

const capturedLayerHandlers = vi.hoisted(
  () => new Map<string, Record<string, (e: unknown) => void>>(),
);

vi.mock("leaflet", () => ({
  default: {
    geoJSON: vi.fn((geoData, options) => {
      capturedLayerHandlers.clear();
      if (Array.isArray(geoData?.features)) {
        for (const feature of geoData.features) {
          if (options?.style) options.style(feature);
          if (options?.onEachFeature) {
            const mockLayer = {
              bindTooltip: vi.fn(),
              bringToFront: vi.fn(),
              setStyle: vi.fn(),
              getBounds: vi.fn().mockReturnValue("mock-bounds"),
              on: vi.fn((handlers: Record<string, (e: unknown) => void>) => {
                capturedLayerHandlers.set(
                  feature.properties.code as string,
                  handlers,
                );
              }),
            };
            options.onEachFeature(feature, mockLayer);
          }
        }
      }
      return { addTo: vi.fn().mockReturnThis(), resetStyle: vi.fn() };
    }),
    map: vi.fn(),
  },
}));

import ZonesExplorer from "@/pages/caches/ZonesExplorer.vue";

beforeEach(() => {
  vi.clearAllMocks();
  mockGetResponses.clear();
});

describe("ZonesExplorer - World view", () => {
  it("fetches countries and level-0 zones on mount", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);

    mount(ZonesExplorer);
    await flushPromises();

    expect(mockFetchCountries).toHaveBeenCalled();
    expect(mockFetchZones).toHaveBeenCalledWith(0);
  });

  it("lists countries with finds as clickable, in the found group", async () => {
    mockFetchCountries.mockResolvedValueOnce([
      { code: "FR", name: "France" },
      { code: "DE", name: "Allemagne" },
    ]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();

    const found = wrapper.find('[data-testid="world-found-group"]');
    expect(found.text()).toContain("France");
    expect(found.text()).not.toContain("Allemagne");
  });

  it("lists countries without finds in the non-clickable group", async () => {
    mockFetchCountries.mockResolvedValueOnce([
      { code: "FR", name: "France" },
      { code: "DE", name: "Allemagne" },
    ]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();

    const empty = wrapper.find('[data-testid="world-empty-group"]');
    expect(empty.text()).toContain("Allemagne");
    const disabledItem = empty.find("li");
    expect(disabledItem.find("button").exists()).toBe(false);
  });

  it("drills into a country on click", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockFetchZones.mockResolvedValueOnce([]); // level-1 call after drilling in

    const wrapper = mount(ZonesExplorer);
    await flushPromises();

    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="map-base"]').exists()).toBe(true);
    expect(mockFetchZones).toHaveBeenCalledWith(1, "FR", []);
  });
});

describe("ZonesExplorer - Country view", () => {
  const geoData = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { code: "84", nom: "Auvergne-Rhône-Alpes" },
        geometry: null,
      },
    ],
  };

  it("fetches the country-level geojson and level-1 zone counts when drilling in", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockGetResponses.set("/geo/FR/adm1.geojson", geoData);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR-84", name: "Auvergne-Rhône-Alpes", cache_count: 3 },
    ]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    expect(mockGet).toHaveBeenCalledWith("/geo/FR/adm1.geojson");
    expect(mockFetchZones).toHaveBeenCalledWith(1, "FR", []);
  });

  it("shows a not-available message when the geojson 404s", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockGetResponses.set("/geo/FR/adm1.geojson", new Error("404"));
    mockFetchZones.mockResolvedValueOnce([]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="geo-unavailable"]').exists()).toBe(true);
  });
});
