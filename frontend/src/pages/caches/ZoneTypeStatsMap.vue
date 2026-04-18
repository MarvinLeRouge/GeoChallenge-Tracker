<template>
  <div class="absolute inset-0 flex flex-col">
    <!-- Toolbar -->
    <div
      class="absolute top-3 left-1/2 -translate-x-1/2 z-[1000] flex items-center gap-3 bg-white rounded-lg shadow-md px-3 py-2 text-sm"
    >
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
        Cliquez sur une zone pour la répartition par type
      </div>
    </div>

    <!-- Map -->
    <MapBase :zoom="6" @ready="onMapReady" />

    <!-- Zone type stats popover -->
    <div
      v-if="popoverVisible && popoverStats"
      class="absolute z-[1001] bg-white rounded-lg shadow-xl border border-gray-200 w-64 text-sm"
      :style="{ top: popoverPos.y + 'px', left: popoverPos.x + 'px' }"
    >
      <div class="flex items-start justify-between p-3 pb-1">
        <div class="font-semibold text-gray-900">{{ popoverStats.name }}</div>
        <button
          class="text-gray-400 hover:text-gray-600 ml-2 shrink-0"
          @click="closePopover"
        >
          ✕
        </button>
      </div>
      <div class="px-3 pb-1 text-gray-500 text-xs">
        {{ totalCount.toLocaleString("fr-FR") }} cache{{
          totalCount > 1 ? "s" : ""
        }}
        trouvée{{ totalCount > 1 ? "s" : "" }}
      </div>
      <hr class="my-1 border-gray-100" />
      <table class="w-full text-xs pb-2">
        <tbody>
          <tr
            v-for="item in popoverStats.type_counts"
            :key="item.type_code"
            :class="item.count === 0 ? 'bg-red-50' : ''"
          >
            <td
              :class="[
                'px-3 py-0.5 text-gray-700',
                item.count === 0 ? 'italic' : '',
              ]"
            >
              <span class="flex items-center gap-1">
                <XCircleIcon
                  v-if="item.count === 0"
                  class="w-3.5 h-3.5 shrink-0 text-red-500"
                  aria-hidden="true"
                />
                {{ item.type_name }}
              </span>
            </td>
            <td
              :class="[
                'px-3 py-0.5 text-right tabular-nums text-gray-700',
                item.count === 0 ? 'italic' : 'font-medium',
              ]"
            >
              {{ item.count.toLocaleString("fr-FR") }}
            </td>
          </tr>
        </tbody>
      </table>
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
import { ref, computed, onUnmounted } from "vue";
import L from "leaflet";
import type { GeoJsonObject } from "geojson";
import { XCircleIcon } from "@heroicons/vue/24/outline";
import MapBase from "@/components/map/MapBase.vue";
import { useZones } from "@/composables/useZones";
import api from "@/api/http";
import type { ZoneListItem, ZoneTypeStatsResponse } from "@/types/zones";

// ── Constants ───────────────────────────────────────────────────────────────

const COLOR_LOW = "#edf8fb";
const COLOR_HIGH = "#006d2c";
const COLOR_HOVER = "#fbbf24";
const COLOR_ZERO = "#fca5a5";
const WEIGHT_DEFAULT = 1;
const WEIGHT_HOVER = 2;

// ── State ────────────────────────────────────────────────────────────────────

const { loading, fetchZones, fetchZoneTypeStats } = useZones();

const currentLevel = ref<1 | 2>(1);

const popoverVisible = ref(false);
const popoverStats = ref<ZoneTypeStatsResponse | null>(null);
const popoverPos = ref({ x: 16, y: 60 });

let leafletMap: L.Map | null = null;
let choroplethLayer: L.GeoJSON | null = null;

// ── Derived ──────────────────────────────────────────────────────────────────

const totalCount = computed(() =>
  popoverStats.value
    ? popoverStats.value.type_counts.reduce((s, t) => s + t.count, 0)
    : 0,
);

// ── Choropleth helpers ───────────────────────────────────────────────────────

function interpolateColor(t: number): string {
  const low = [0xed, 0xf8, 0xfb];
  const high = [0x00, 0x6d, 0x2c];
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

async function renderLevel(level: 1 | 2) {
  if (!leafletMap) return;

  const geoPath =
    level === 1 ? "/geo/FR/regions.geojson" : "/geo/FR/departements.geojson";
  const [geoData, zoneItems] = await Promise.all([
    fetchGeoJson(geoPath),
    fetchZones("FR", level),
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
      x: Math.min(containerPoint.x + 12, window.innerWidth - 270),
      y: Math.min(
        Math.max(containerPoint.y - 20, 60),
        window.innerHeight - 500,
      ),
    };
  }

  const stats = await fetchZoneTypeStats(code, level);
  if (stats) {
    popoverStats.value = stats;
    popoverVisible.value = true;
  }
}

function closePopover() {
  popoverVisible.value = false;
  popoverStats.value = null;
}

// ── Map ready ────────────────────────────────────────────────────────────────

async function onMapReady(map: L.Map) {
  leafletMap = map;
  leafletMap.on("click", closePopover);
  await renderLevel(1);
}

// ── Cleanup ───────────────────────────────────────────────────────────────────

onUnmounted(() => {
  leafletMap?.off("click", closePopover);
  removeChoropleth();
  leafletMap = null;
});
</script>
