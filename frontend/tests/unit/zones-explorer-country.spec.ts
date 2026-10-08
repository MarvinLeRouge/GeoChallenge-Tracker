import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { ref } from "vue";

// Builds a minimal object that passes axios's isAxiosError() check (it only
// checks e.isAxiosError === true), mirroring tests/unit/api-error-handler.spec.ts.
const axiosError = (opts: {
  response?: { status: number; data?: unknown };
  request?: unknown;
  message?: string;
}) => ({
  isAxiosError: true,
  response: opts.response ?? null,
  request: opts.request ?? null,
  message: opts.message ?? "Axios error",
});

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
      const isAxiosErrorShaped =
        typeof value === "object" &&
        value !== null &&
        (value as { isAxiosError?: boolean }).isAxiosError === true;
      if (value instanceof Error || isAxiosErrorShaped) {
        return Promise.reject(value);
      }
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
  // A real Vue ref (not a plain { value: null } object) so that ZonesExplorer
  // assigning error.value directly (e.g. from fetchGeoJson) triggers a
  // template re-render, exactly like the real composable's ref.
  useZones: () => ({
    loading: mockLoading,
    error: ref<string | null>(null),
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
      return {
        addTo: vi.fn().mockReturnThis(),
        resetStyle: vi.fn(),
        getBounds: vi.fn().mockReturnValue("mock-country-bounds"),
      };
    }),
    map: vi.fn(),
  },
}));

import ZonesExplorer from "@/pages/caches/ZonesExplorer.vue";

beforeEach(() => {
  vi.clearAllMocks();
  mockGetResponses.clear();
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
    // A genuine axios 404 (geojson genuinely not uploaded yet), not just any
    // failure - see the "surfaces a non-404 geojson failure" test below for
    // the distinction the fix introduces.
    mockGetResponses.set(
      "/geo/FR/adm1.geojson",
      axiosError({ response: { status: 404, data: {} } }),
    );
    mockFetchZones.mockResolvedValueOnce([]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="geo-unavailable"]').exists()).toBe(true);
  });

  it("re-renders the choropleth when the type filter changes at Country level", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockGetResponses.set("/geo/FR/adm1.geojson", geoData);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR-84", name: "Auvergne-Rhône-Alpes", cache_count: 3 },
    ]);
    mockGetResponses.set("/cache_types", [
      { code: "traditional", name: "Traditional" },
    ]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    mockFetchZones.mockResolvedValueOnce([
      { code: "FR-84", name: "Auvergne-Rhône-Alpes", cache_count: 1 },
    ]);

    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    await wrapper.find('input[type="checkbox"]').setValue(true);
    await flushPromises();

    expect(mockFetchZones).toHaveBeenLastCalledWith(1, "FR", ["traditional"]);
  });

  it("does not drill into a region when clicking a zero-count feature at Country level", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockGetResponses.set("/geo/FR/adm1.geojson", geoData);
    // No zone item for "FR-84" - the feature's computed count is 0.
    mockFetchZones.mockResolvedValueOnce([]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    const handlers = capturedLayerHandlers.get("84");
    expect(handlers).toBeDefined();
    handlers?.click({ latlng: { lat: 45.5, lng: 5.5 } });
    await flushPromises();

    expect(
      mockGet.mock.calls.some((c) => c[0] === "/geo/FR/adm2.geojson"),
    ).toBe(false);
    expect(mockFetchZoneDetail).not.toHaveBeenCalled();
    expect(mockLeafletMap.fitBounds).not.toHaveBeenCalledWith("mock-bounds");
    expect(wrapper.find('[data-testid="zone-popover"]').exists()).toBe(false);
  });

  it("returns to the World view when going back from Country level", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockGetResponses.set("/geo/FR/adm1.geojson", geoData);
    mockFetchZones.mockResolvedValueOnce([]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="map-base"]').exists()).toBe(true);

    const backButton = wrapper
      .findAll("button")
      .find((b) => b.text().includes("Retour"));
    expect(backButton).toBeDefined();
    await backButton!.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="map-base"]').exists()).toBe(false);
    const found = wrapper.find('[data-testid="world-found-group"]');
    expect(found.exists()).toBe(true);
    expect(found.text()).toContain("France");
  });
});
