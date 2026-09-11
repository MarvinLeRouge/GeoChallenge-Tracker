<!-- frontend/src/pages/caches/ZonesExplorer.vue -->
<template>
  <div class="absolute inset-0 flex flex-col">
    <div
      v-if="level === 0"
      class="p-4 max-w-2xl mx-auto overflow-y-auto w-full"
    >
      <h1 class="text-lg font-semibold mb-4 dark:text-gray-100">
        Zones administratives
      </h1>
      <div
        v-if="error"
        class="text-center text-red-600 text-sm dark:text-red-400"
      >
        {{ error }}
      </div>
      <div v-if="loading">
        <LoadingIndicator label="Chargement…" />
      </div>
      <template v-else>
        <section v-if="foundCountries.length" class="mb-4">
          <h2
            class="text-xs font-semibold text-gray-500 uppercase mb-2 dark:text-gray-400"
          >
            Pays avec trouvailles
          </h2>
          <ul data-testid="world-found-group" class="space-y-1">
            <li v-for="c in foundCountries" :key="c.code">
              <button
                type="button"
                class="w-full text-left px-3 py-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 dark:text-gray-200"
                @click="drillToCountry(c.code)"
              >
                <span>{{ c.name }}</span>
                <span class="text-gray-400 text-xs ml-2">{{
                  c.cache_count
                }}</span>
              </button>
            </li>
          </ul>
        </section>
        <section v-if="emptyCountries.length">
          <h2
            class="text-xs font-semibold text-gray-400 uppercase mb-2 dark:text-gray-500"
          >
            Autres pays
          </h2>
          <ul data-testid="world-empty-group" class="space-y-1">
            <li
              v-for="c in emptyCountries"
              :key="c.code"
              class="px-3 py-2 text-gray-400 cursor-not-allowed dark:text-gray-600"
            >
              {{ c.name }}
            </li>
          </ul>
        </section>
      </template>
    </div>

    <template v-else>
      <div
        class="absolute top-3 left-1/2 -translate-x-1/2 z-20 flex items-center gap-3 bg-white rounded-lg shadow-md px-3 py-2 text-sm dark:bg-gray-900"
      >
        <button
          type="button"
          class="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          @click="goBack"
        >
          ← Retour
        </button>
        <div class="h-4 w-px bg-gray-200 dark:bg-gray-700" />
        <TypeFilterDropdown v-model="selectedTypes" :options="cacheTypes" />
      </div>

      <div
        v-if="geoUnavailable"
        data-testid="geo-unavailable"
        class="absolute inset-0 z-10 flex items-center justify-center text-gray-500 dark:text-gray-400"
      >
        Données GeoJSON pas encore disponibles pour ce pays.
      </div>

      <MapBase ref="mapRef" :zoom="6" @ready="onMapReady" />

      <div
        v-if="popoverVisible && popoverDetail"
        data-testid="zone-popover"
        class="absolute z-30 bg-white rounded-lg shadow-xl border border-gray-200 w-72 text-sm dark:bg-gray-900 dark:border-gray-700"
        :style="{ top: popoverPos.y + 'px', left: popoverPos.x + 'px' }"
      >
        <div class="flex items-start justify-between p-3 pb-1">
          <div class="font-semibold text-gray-900 dark:text-gray-100">
            {{ popoverDetail.name }}
          </div>
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600 ml-2 shrink-0 dark:text-gray-500 dark:hover:text-gray-300"
            @click="closePopover"
          >
            ✕
          </button>
        </div>
        <div class="px-3 pb-1 text-gray-500 text-xs dark:text-gray-400">
          {{ popoverDetail.cache_count.toLocaleString("fr-FR") }} cache{{
            popoverDetail.cache_count > 1 ? "s" : ""
          }}
        </div>
        <hr class="my-1 border-gray-100 dark:border-gray-800" />
        <ul class="px-3 pb-2 space-y-1">
          <li
            v-for="t in popoverDetail.type_counts"
            :key="t.type_code"
            class="flex items-center justify-between text-gray-700 dark:text-gray-300"
          >
            <span>{{ t.type_name }}</span>
            <span class="text-gray-400">{{ t.count }}</span>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import L from "leaflet";
import type { GeoJsonObject } from "geojson";
import MapBase from "@/components/map/MapBase.vue";
import LoadingIndicator from "@/components/ui/LoadingIndicator.vue";
import TypeFilterDropdown from "@/components/zones/TypeFilterDropdown.vue";
import { useZones } from "@/composables/useZones";
import { useApiErrorHandler } from "@/composables/useApiErrorHandler";
import api from "@/api/http";
import type { Country, ZoneDetail, ZoneListItem } from "@/types/zones";

// ── Constants ───────────────────────────────────────────────────────────────

const COLOR_LOW = "#edf8fb";
const COLOR_HIGH = "#006d2c";
const COLOR_HOVER = "#fbbf24";
const COLOR_ZERO = "#fca5a5";

// ── State ────────────────────────────────────────────────────────────────────

const mapRef = ref<InstanceType<typeof MapBase> | null>(null);
const { loading, error, fetchCountries, fetchZones, fetchZoneDetail } =
  useZones();
const { handleApiError } = useApiErrorHandler();

const level = ref<0 | 1 | 2>(0);
const selectedCountry = ref<string | null>(null);
const selectedRegion = ref<string | null>(null);
const selectedTypes = ref<string[]>([]);
const geoUnavailable = ref(false);
const popoverVisible = ref(false);
const popoverDetail = ref<ZoneDetail | null>(null);
const popoverPos = ref({ x: 16, y: 60 });

const allCountries = ref<Country[]>([]);
const zonesLevel0 = ref<ZoneListItem[]>([]);

interface CacheTypeOption {
  code: string;
  name: string;
}
const cacheTypes = ref<CacheTypeOption[]>([]);

let leafletMap: L.Map | null = null;
let choroplethLayer: L.GeoJSON | null = null;

// ── World view derived lists ────────────────────────────────────────────────

const foundCountries = computed(() =>
  [...zonesLevel0.value].sort((a, b) => a.name.localeCompare(b.name)),
);

const emptyCountries = computed(() => {
  const foundCodes = new Set(zonesLevel0.value.map((z) => z.code));
  return allCountries.value
    .filter((c) => !foundCodes.has(c.code))
    .sort((a, b) => a.name.localeCompare(b.name));
});

// ── World loading ────────────────────────────────────────────────────────────

async function loadWorld() {
  const [countries, zones] = await Promise.all([
    fetchCountries(),
    fetchZones(0),
  ]);
  allCountries.value = countries;
  zonesLevel0.value = zones;
}

async function loadCacheTypes() {
  try {
    const { data } =
      await api.get<{ code: string; name: string }[]>("/cache_types");
    cacheTypes.value = data.map((t) => ({ code: t.code, name: t.name }));
  } catch (err) {
    // Non-blocking: the type filter simply stays empty, but the failure
    // must still be diagnosable rather than silently discarded.
    console.error("Failed to load cache types", err);
  }
}

onMounted(() => {
  loadWorld();
  loadCacheTypes();
});

// ── Choropleth helpers ───────────────────────────────────────────────────────

function hexToRgb(hex: string): [number, number, number] {
  const value = parseInt(hex.slice(1), 16);
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff];
}

function interpolateColor(t: number): string {
  const low = hexToRgb(COLOR_LOW);
  const high = hexToRgb(COLOR_HIGH);
  const r = Math.round(low[0] + t * (high[0] - low[0]));
  const g = Math.round(low[1] + t * (high[1] - low[1]));
  const b = Math.round(low[2] + t * (high[2] - low[2]));
  return `rgb(${r},${g},${b})`;
}

function buildCountMap(items: ZoneListItem[]): Map<string, number> {
  return new Map(items.map((z) => [z.code, z.cache_count]));
}

function maxCount(items: ZoneListItem[]): number {
  return items.reduce((m, z) => Math.max(m, z.cache_count), 1);
}

interface GeoJsonFetchResult {
  data: GeoJsonObject | null;
  /** True only for a genuine 404 (geojson genuinely not uploaded yet). */
  notFound: boolean;
}

async function fetchGeoJson(path: string): Promise<GeoJsonFetchResult> {
  try {
    const { data } = await api.get<GeoJsonObject>(path);
    return { data, notFound: false };
  } catch (err) {
    const apiError = handleApiError(err);
    if (apiError.status === 404) {
      return { data: null, notFound: true };
    }
    // A real failure (network error, 500, ...) must not be presented as
    // "not available yet" - log it and surface it through the shared
    // error banner instead.
    console.error("Failed to fetch geojson", path, err);
    error.value = apiError.message;
    return { data: null, notFound: false };
  }
}

function removeChoropleth() {
  if (choroplethLayer && leafletMap) {
    leafletMap.removeLayer(choroplethLayer);
    choroplethLayer = null;
  }
}

let currentRenderToken = 0;

async function renderChoropleth(
  zoomLevel: 1 | 2,
  country: string,
  fit = false,
) {
  if (!leafletMap) return;
  const token = ++currentRenderToken;

  const geoPath = `/geo/${country}/adm${zoomLevel}.geojson`;
  const [geoResult, zoneItems] = await Promise.all([
    fetchGeoJson(geoPath),
    fetchZones(zoomLevel, country, selectedTypes.value),
  ]);

  // A newer render started (or the map was torn down) while this one was
  // in flight - drop this stale result rather than let it overwrite the
  // current, more recent state.
  if (token !== currentRenderToken || !leafletMap) return;

  if (!geoResult.data) {
    geoUnavailable.value = geoResult.notFound;
    removeChoropleth();
    return;
  }
  geoUnavailable.value = false;

  const countMap = buildCountMap(zoneItems);
  const max = maxCount(zoneItems);

  removeChoropleth();

  choroplethLayer = L.geoJSON(geoResult.data, {
    style(feature) {
      const featureCode = feature?.properties?.code as string | undefined;
      const zoneCode = featureCode ? `${country}-${featureCode}` : null;
      const count = zoneCode ? (countMap.get(zoneCode) ?? 0) : 0;
      const t = count > 0 ? Math.sqrt(count / max) : 0;
      return {
        fillColor: count > 0 ? interpolateColor(t) : COLOR_ZERO,
        fillOpacity: 0.75,
        color: "#6b7280",
        weight: 1,
      };
    },
    onEachFeature(feature, layer) {
      const featureCode = feature?.properties?.code as string | undefined;
      const zoneCode = featureCode ? `${country}-${featureCode}` : null;
      const zoneName = feature?.properties?.nom as string | undefined;
      const count = zoneCode ? (countMap.get(zoneCode) ?? 0) : 0;

      layer.bindTooltip(
        `<strong>${zoneName ?? zoneCode ?? "?"}</strong><br/>${count.toLocaleString("fr-FR")} cache${count > 1 ? "s" : ""}`,
        { sticky: true, opacity: 0.9 },
      );

      layer.on({
        mouseover(e) {
          const l = e.target as L.Path;
          l.setStyle({ weight: 2, color: COLOR_HOVER });
          l.bringToFront();
        },
        mouseout(e) {
          choroplethLayer?.resetStyle(e.target as L.Path);
        },
        click(e) {
          if (!zoneCode || count === 0) return;
          onZoneClick(zoneCode, zoomLevel, layer as L.Polygon, e);
        },
      });
    },
  });

  choroplethLayer.addTo(leafletMap);

  // Only fit the viewport when entering a country for the first time; a
  // type-filter re-render must not yank the user's current viewport back.
  if (fit) {
    leafletMap.fitBounds(choroplethLayer.getBounds());
  }
}

// ── Zone click (level-1 drills to Region, level-2 opens popup) ─────────────

async function onZoneClick(
  code: string,
  zoomLevel: 1 | 2,
  layer: L.Polygon,
  event: L.LeafletMouseEvent,
) {
  if (zoomLevel === 1) {
    selectedRegion.value = code;
    level.value = 2;
    if (leafletMap) leafletMap.fitBounds(layer.getBounds());
    await renderChoropleth(2, selectedCountry.value!);
    return;
  }
  await openPopover(code, event, zoomLevel);
}

async function openPopover(
  code: string,
  event: L.LeafletMouseEvent,
  zoomLevel: 1 | 2,
) {
  popoverVisible.value = false;

  const containerPoint = leafletMap?.latLngToContainerPoint(event.latlng);
  if (containerPoint) {
    popoverPos.value = {
      x: Math.min(containerPoint.x + 12, window.innerWidth - 300),
      y: Math.min(
        Math.max(containerPoint.y - 20, 60),
        window.innerHeight - 420,
      ),
    };
  }

  const detail = await fetchZoneDetail(code, zoomLevel);
  if (detail) {
    popoverDetail.value = detail;
    popoverVisible.value = true;
  }
}

function closePopover() {
  popoverVisible.value = false;
  popoverDetail.value = null;
}

// ── World -> Country drill-down ─────────────────────────────────────────────

function drillToCountry(code: string) {
  selectedCountry.value = code;
  level.value = 1;
}

function goBack() {
  closePopover();
  if (level.value === 2) {
    level.value = 1;
    selectedRegion.value = null;
    if (selectedCountry.value) renderChoropleth(1, selectedCountry.value);
    return;
  }
  if (level.value === 1) {
    level.value = 0;
    selectedCountry.value = null;
    removeChoropleth();
    leafletMap = null;
  }
}

watch(selectedTypes, async () => {
  if (level.value === 1 && selectedCountry.value) {
    await renderChoropleth(1, selectedCountry.value);
  } else if (level.value === 2 && selectedCountry.value) {
    await renderChoropleth(2, selectedCountry.value);
  }
});

async function onMapReady(map: L.Map) {
  leafletMap = map;
  if (level.value === 1 && selectedCountry.value) {
    await renderChoropleth(1, selectedCountry.value, true);
  }
}

onUnmounted(() => {
  removeChoropleth();
  leafletMap = null;
});
</script>
