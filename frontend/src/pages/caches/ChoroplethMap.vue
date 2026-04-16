<template>
  <div class="absolute inset-0 flex flex-col">
    <!-- Toolbar -->
    <div
      class="absolute top-3 left-1/2 -translate-x-1/2 z-[1000] flex items-center gap-3 bg-white rounded-lg shadow-md px-3 py-2 text-sm"
    >
      <!-- Level toggle -->
      <div class="flex items-center gap-0.5 bg-gray-100 rounded-md p-0.5">
        <button
          :class="[
            'px-3 py-1 text-xs rounded font-medium transition-colors',
            currentLevel === 1
              ? 'bg-white shadow text-gray-900'
              : 'text-gray-500 hover:text-gray-700',
          ]"
          @click="setLevel(1)"
        >
          Régions
        </button>
        <button
          :class="[
            'px-3 py-1 text-xs rounded font-medium transition-colors',
            currentLevel === 2
              ? 'bg-white shadow text-gray-900'
              : 'text-gray-500 hover:text-gray-700',
          ]"
          @click="setLevel(2)"
        >
          Départements
        </button>
      </div>

      <div class="h-4 w-px bg-gray-200" />

      <!-- Type filter -->
      <select
        v-model="selectedType"
        class="border border-gray-200 rounded px-2 py-1 text-xs text-gray-700 bg-white"
        @change="reloadCounts"
      >
        <option value="">Tous les types</option>
        <option v-for="t in cacheTypes" :key="t.code" :value="t.code">
          {{ t.label }}
        </option>
      </select>
    </div>

    <!-- Legend -->
    <div
      class="absolute bottom-6 right-3 z-[1000] bg-white rounded-lg shadow-md px-3 py-2 text-xs text-gray-700"
    >
      <div class="font-medium mb-1">Caches</div>
      <div class="flex items-center gap-1">
        <div class="w-3 h-3 rounded-sm" :style="{ background: COLOR_ZERO }" />
        <span>0</span>
        <div
          class="w-3 h-3 rounded-sm mx-1"
          :style="{ background: COLOR_LOW }"
        />
        <span>Peu</span>
        <div
          class="w-12 h-3 rounded-sm mx-1"
          :style="{
            background: `linear-gradient(to right, ${COLOR_LOW}, ${COLOR_HIGH})`,
          }"
        />
        <span>Beaucoup</span>
        <div class="w-3 h-3 rounded-sm" :style="{ background: COLOR_HIGH }" />
      </div>
      <div class="mt-1 text-gray-400 text-[10px]">
        Cliquez sur une zone pour les détails
      </div>
    </div>

    <!-- Map -->
    <MapBase ref="mapRef" :zoom="6" @ready="onMapReady" />

    <!-- Zone detail popover -->
    <div
      v-if="popoverVisible && popoverDetail"
      class="absolute z-[1001] bg-white rounded-lg shadow-xl border border-gray-200 w-72 text-sm"
      :style="{ top: popoverPos.y + 'px', left: popoverPos.x + 'px' }"
    >
      <div class="flex items-start justify-between p-3 pb-1">
        <div class="font-semibold text-gray-900">{{ popoverDetail.name }}</div>
        <button
          class="text-gray-400 hover:text-gray-600 ml-2 shrink-0"
          @click="closePopover"
        >
          ✕
        </button>
      </div>
      <div class="px-3 pb-1 text-gray-500 text-xs">
        {{ popoverDetail.cache_count.toLocaleString("fr-FR") }} cache{{
          popoverDetail.cache_count > 1 ? "s" : ""
        }}
        <span v-if="selectedType" class="italic"> ({{ selectedType }})</span>
      </div>
      <hr class="my-1 border-gray-100" />
      <ul v-if="popoverDetail.caches.length" class="px-3 pb-2 space-y-1">
        <li
          v-for="cache in popoverDetail.caches"
          :key="cache.GC"
          class="flex items-center gap-1 text-gray-700"
        >
          <span class="text-gray-400 text-xs shrink-0">{{ cache.GC }}</span>
          <span class="truncate">{{ cache.title }}</span>
          <span
            v-if="cache.difficulty && cache.terrain"
            class="text-gray-400 text-xs shrink-0"
          >
            D{{ cache.difficulty }}/T{{ cache.terrain }}
          </span>
        </li>
      </ul>
      <div v-else class="px-3 pb-2 text-gray-400 text-xs italic">
        Aucune cache pour ce filtre.
      </div>
      <div
        v-if="popoverDetail.cache_count > popoverDetail.caches.length"
        class="px-3 pb-3"
      >
        <router-link
          :to="`/caches/within-bbox`"
          class="text-blue-600 hover:underline text-xs"
        >
          Voir les
          {{ popoverDetail.cache_count.toLocaleString("fr-FR") }} caches →
        </router-link>
      </div>
    </div>

    <!-- Loading overlay -->
    <div
      v-if="loading"
      class="absolute inset-0 z-[999] flex items-center justify-center bg-white/40 pointer-events-none"
    >
      <div class="bg-white rounded-lg shadow px-4 py-2 text-sm text-gray-600">
        Chargement…
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from "vue";
import L from "leaflet";
import type { GeoJsonObject } from "geojson";
import MapBase from "@/components/map/MapBase.vue";
import { useZones } from "@/composables/useZones";
import api from "@/api/http";
import type { ZoneDetail, ZoneListItem } from "@/types/zones";

// ── Constants ───────────────────────────────────────────────────────────────

const COLOR_LOW = "#edf8fb";
const COLOR_HIGH = "#006d2c";
const COLOR_HOVER = "#fbbf24";
const COLOR_ZERO = "#fca5a5"; // red-300 — zones with 0 caches
const WEIGHT_DEFAULT = 1;
const WEIGHT_HOVER = 2;

// ── State ────────────────────────────────────────────────────────────────────

const mapRef = ref<InstanceType<typeof MapBase> | null>(null);
const { loading, fetchZones, fetchZoneDetail } = useZones();

const currentLevel = ref<1 | 2>(1);
const selectedType = ref<string>("");

const popoverVisible = ref(false);
const popoverDetail = ref<ZoneDetail | null>(null);
const popoverPos = ref({ x: 16, y: 60 });

interface CacheTypeOption {
  code: string;
  label: string;
}
const cacheTypes = ref<CacheTypeOption[]>([]);

let leafletMap: L.Map | null = null;
let choroplethLayer: L.GeoJSON | null = null;

// ── Choropleth helpers ───────────────────────────────────────────────────────

function interpolateColor(t: number): string {
  const low = [0xed, 0xf8, 0xfb]; // #edf8fb
  const high = [0x00, 0x6d, 0x2c]; // #006d2c
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

// ── GeoJSON fetch ────────────────────────────────────────────────────────────

async function fetchGeoJson(path: string): Promise<GeoJsonObject | null> {
  try {
    const { data } = await api.get<GeoJsonObject>(path);
    return data;
  } catch {
    return null;
  }
}

// ── Layer management ─────────────────────────────────────────────────────────

function removeChoropleth() {
  if (choroplethLayer && leafletMap) {
    leafletMap.removeLayer(choroplethLayer);
    choroplethLayer = null;
  }
}

function getTypeCode(): string | undefined {
  return selectedType.value || undefined;
}

async function renderLevel(level: 1 | 2) {
  if (!leafletMap) return;

  const geoPath =
    level === 1 ? "/geo/FR/regions.geojson" : "/geo/FR/departements.geojson";
  const [geoData, zoneItems] = await Promise.all([
    fetchGeoJson(geoPath),
    fetchZones("FR", level, getTypeCode()),
  ]);

  if (!geoData) return;

  const countMap = buildCountMap(zoneItems);
  const max = maxCount(zoneItems);

  removeChoropleth();

  choroplethLayer = L.geoJSON(geoData, {
    style(feature) {
      const featureCode = feature?.properties?.code as string | undefined;
      const zoneCode = featureCode ? `FR-${featureCode}` : null;
      const count = zoneCode ? (countMap.get(zoneCode) ?? 0) : 0;
      const t = count > 0 ? Math.sqrt(count / max) : 0;
      return {
        fillColor: count > 0 ? interpolateColor(t) : COLOR_ZERO,
        fillOpacity: 0.75,
        color: "#6b7280",
        weight: WEIGHT_DEFAULT,
      };
    },
    onEachFeature(feature, layer) {
      const featureCode = feature?.properties?.code as string | undefined;
      const zoneCode = featureCode ? `FR-${featureCode}` : null;
      const zoneName = feature?.properties?.nom as string | undefined;
      const count = zoneCode ? (countMap.get(zoneCode) ?? 0) : 0;

      layer.bindTooltip(
        `<strong>${zoneName ?? zoneCode ?? "?"}</strong><br/>${count.toLocaleString("fr-FR")} cache${count > 1 ? "s" : ""}`,
        { sticky: true, opacity: 0.9 },
      );

      layer.on({
        mouseover(e) {
          const l = e.target as L.Path;
          l.setStyle({ weight: WEIGHT_HOVER, color: COLOR_HOVER });
          l.bringToFront();
        },
        mouseout(e) {
          choroplethLayer?.resetStyle(e.target as L.Path);
        },
        click(e) {
          if (!zoneCode) return;
          openPopover(zoneCode, e, level);
        },
      });
    },
  });

  choroplethLayer.addTo(leafletMap);
}

// ── Level switch ──────────────────────────────────────────────────────────────

async function setLevel(level: 1 | 2) {
  if (level === currentLevel.value) return;
  currentLevel.value = level;
  closePopover();
  await renderLevel(level);
}

// ── Popover ──────────────────────────────────────────────────────────────────

async function openPopover(
  code: string,
  event: L.LeafletMouseEvent,
  level: 1 | 2,
) {
  popoverVisible.value = false;

  const containerPoint = leafletMap?.latLngToContainerPoint(event.latlng);
  if (containerPoint) {
    popoverPos.value = {
      x: Math.min(containerPoint.x + 12, window.innerWidth - 300),
      y: Math.max(containerPoint.y - 20, 60),
    };
  }

  const detail = await fetchZoneDetail(code, getTypeCode(), level);
  if (detail) {
    popoverDetail.value = detail;
    popoverVisible.value = true;
  }
}

function closePopover() {
  popoverVisible.value = false;
  popoverDetail.value = null;
}

// ── Type filter reload ───────────────────────────────────────────────────────

async function reloadCounts() {
  closePopover();
  await renderLevel(currentLevel.value);
}

// ── Map ready ────────────────────────────────────────────────────────────────

async function onMapReady(map: L.Map) {
  leafletMap = map;

  try {
    const { data } =
      await api.get<{ code: string; name: string }[]>("/cache_types");
    cacheTypes.value = data.map((t) => ({ code: t.code, label: t.name }));
  } catch {
    // non-blocking
  }

  await renderLevel(1);
}

// ── Cleanup ───────────────────────────────────────────────────────────────────

onUnmounted(() => {
  removeChoropleth();
  leafletMap = null;
});
</script>
