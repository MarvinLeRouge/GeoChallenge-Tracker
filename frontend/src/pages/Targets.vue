<template>
  <div class="absolute inset-0">
    <!-- Map layer -->
    <div class="absolute inset-0 z-0">
      <MapBase
        ref="mapRef"
        @ready="onMapReady"
        @click="onMapClick"
        @pick="onMapPick"
      />
    </div>

    <!-- Overlay panel -->
    <div
      class="absolute left-2 right-2 bottom-2 z-40 flex flex-col gap-2 with-fab"
    >
      <div class="rounded-lg bg-white/95 border p-2 shadow">
        <!-- Evaluating state -->
        <div
          v-if="evaluating"
          class="flex items-center gap-2 text-sm text-indigo-700"
        >
          <ArrowPathIcon class="w-4 h-4 animate-spin" aria-hidden="true" />
          Mise à jour des targets en cours…
        </div>

        <!-- Loading targets -->
        <div
          v-else-if="loading"
          class="flex items-center gap-2 text-sm text-gray-500"
        >
          <ArrowPathIcon class="w-4 h-4 animate-spin" aria-hidden="true" />
          Chargement des targets…
        </div>

        <!-- Results -->
        <div v-else>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">
              {{ nbItems > 0 ? `${nbItems} target(s)` : "Aucune target" }}
            </span>

            <!-- Nearby mode toggle -->
            <label class="flex items-center gap-1.5 cursor-pointer select-none">
              <span class="text-xs text-gray-600">Proximité</span>
              <button
                type="button"
                role="switch"
                :aria-checked="nearbyMode"
                class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
                :class="nearbyMode ? 'bg-indigo-600' : 'bg-gray-300'"
                @click="toggleNearbyMode"
              >
                <span
                  class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
                  :class="nearbyMode ? 'translate-x-4' : 'translate-x-1'"
                />
              </button>
            </label>
          </div>

          <!-- Nearby controls -->
          <div v-if="nearbyMode" class="flex items-center gap-2 mt-2">
            <!-- Reticle button -->
            <button
              type="button"
              class="border rounded p-1.5"
              :class="
                picking ? 'bg-indigo-100 border-indigo-400' : 'hover:bg-gray-50'
              "
              aria-label="Choisir le centre sur la carte"
              title="Choisir le centre sur la carte"
              @click="startPick"
            >
              <svg
                viewBox="0 0 24 24"
                width="16"
                height="16"
                aria-hidden="true"
              >
                <path
                  d="M11 2v3a1 1 0 002 0V2h-2zm0 17v3h2v-3a1 1 0 10-2 0zM2 11h3a1 1 0 100-2H2v2zm17 0h3v-2h-3a1 1 0 100 2z"
                />
                <circle
                  cx="12"
                  cy="12"
                  r="3"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                />
              </svg>
            </button>

            <!-- Radius input -->
            <input
              v-model.number="radiusKm"
              type="number"
              min="1"
              step="5"
              class="border rounded px-2 py-1 w-16 text-sm"
              @change="onRadiusChange"
            />
            <span class="text-sm text-gray-600">km</span>
          </div>

          <!-- Pick hint -->
          <p v-if="picking" class="text-xs text-indigo-700 mt-1">
            Cliquez sur la carte pour définir le centre…
          </p>

          <!-- Nearby center info -->
          <p
            v-else-if="nearbyMode && nearbyCenter"
            class="text-xs text-gray-500 mt-1"
          >
            Centre : {{ centerLabel }}
          </p>

          <!-- Up-to-date info (normal mode) -->
          <p
            v-else-if="
              !nearbyMode &&
              refreshStatus &&
              !refreshStatus.needs_refresh &&
              refreshStatus.last_targets_evaluated_at
            "
            class="text-xs text-gray-500 mt-1"
          >
            Aucune nouvelle cache depuis la dernière mise à jour ({{
              formatDate(refreshStatus.last_targets_evaluated_at)
            }})
          </p>

          <!-- No import yet -->
          <p
            v-else-if="
              !nearbyMode &&
              refreshStatus &&
              !refreshStatus.last_not_found_import_at
            "
            class="text-xs text-gray-500 mt-1"
          >
            Importez des caches GPX pour voir vos targets.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch } from "vue";
import L from "leaflet";
import "leaflet.markercluster";
import DOMPurify from "dompurify";
import MapBase from "@/components/map/MapBase.vue";
import { useTargets, type TargetItem } from "@/composables/useTargets";
import { useUserProfile } from "@/composables/useUserProfile";
import { getIconFor } from "@/config/cache-icon";
import { ArrowPathIcon } from "@heroicons/vue/24/solid";
import { toast } from "vue-sonner";

const mapRef = ref<InstanceType<typeof MapBase> | null>(null);
let map: L.Map | null = null;
let cluster: L.MarkerClusterGroup | null = null;
let circle: L.Circle | null = null;

const {
  targets,
  nbItems,
  loading,
  evaluating,
  refreshStatus,
  init,
  fetchTargetsNearby,
} = useTargets();
const { location, loadLocation } = useUserProfile();

// --- Nearby mode state ---
const nearbyMode = ref(false);
const nearbyCenter = ref<{ lat: number; lon: number } | null>(null);
const radiusKm = ref(50);
const picking = ref(false);

const centerLabel = computed(() => {
  if (!nearbyCenter.value) return "";
  const { lat, lon } = nearbyCenter.value;
  return `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
});

// --- Map setup ---

function onMapReady(m: L.Map) {
  map = m;
  cluster = L.markerClusterGroup({
    showCoverageOnHover: false,
    spiderfyOnMaxZoom: true,
    disableClusteringAtZoom: 15,
    maxClusterRadius: 60,
  }).addTo(map);
}

// --- Nearby mode ---

async function toggleNearbyMode() {
  nearbyMode.value = !nearbyMode.value;

  if (!nearbyMode.value) {
    // Back to normal mode
    circle?.remove();
    circle = null;
    nearbyCenter.value = null;
    picking.value = false;
    await init();
    return;
  }

  // Activate nearby mode — try declared position first
  const loc = location.value;
  if (loc?.lat != null && loc?.lon != null) {
    await applyNearbyCenter(loc.lat, loc.lon);
  } else {
    toast.info(
      "Aucune position enregistrée — cliquez sur la carte pour définir un centre.",
    );
    picking.value = true;
  }
}

async function applyNearbyCenter(lat: number, lon: number) {
  nearbyCenter.value = { lat, lon };
  drawCircle(lat, lon);
  await fetchTargetsNearby(lat, lon, radiusKm.value);
}

function drawCircle(lat: number, lon: number) {
  if (!map) return;
  circle?.remove();
  circle = L.circle([lat, lon], {
    radius: radiusKm.value * 1000,
    color: "#2563eb",
  }).addTo(map);
  map.fitBounds(circle.getBounds(), { padding: [20, 20], maxZoom: 13 });
}

function startPick() {
  picking.value = true;
  mapRef.value?.enablePick?.();
}

function onMapPick(p: { lat: number; lng: number }) {
  picking.value = false;
  applyNearbyCenter(p.lat, p.lng);
}

function onMapClick(e: L.LeafletMouseEvent) {
  if (!picking.value) return;
  picking.value = false;
  applyNearbyCenter(e.latlng.lat, e.latlng.lng);
}

async function onRadiusChange() {
  if (!nearbyMode.value || !nearbyCenter.value) return;
  const { lat, lon } = nearbyCenter.value;
  drawCircle(lat, lon);
  await fetchTargetsNearby(lat, lon, radiusKm.value);
}

// --- Markers ---

function renderTargetPopup(t: TargetItem): string {
  const gc = DOMPurify.sanitize(t.cache_GC ?? "");
  const title = DOMPurify.sanitize(t.cache_title ?? "(Sans titre)");
  const diff = t.cache_difficulty ?? "-";
  const terr = t.cache_terrain ?? "-";
  const score = typeof t.score === "number" ? (t.score * 100).toFixed(0) : "-";
  const tasks = t.matched_tasks_count ?? 0;

  return `
    <div class="p-2 text-sm leading-snug min-w-[180px]">
      <div class="font-medium">
        ${title} ${gc ? `<span class="text-xs text-gray-500">(${gc})</span>` : ""}
      </div>
      <div class="mt-1 text-xs text-gray-600">
        D/T : ${diff} / ${terr}<br/>
        Score : ${score}%<br/>
        ${tasks > 0 ? `Tâches couvertes : ${tasks}` : ""}
      </div>
      ${
        gc
          ? `
        <div class="mt-2">
          <a class="text-blue-600 underline" target="_blank" rel="noopener"
             href="https://www.geocaching.com/geocache/${gc}">
            Ouvrir sur Geocaching
          </a>
        </div>`
          : ""
      }
    </div>
  `;
}

function plotTargets(items: TargetItem[]) {
  if (!cluster) return;
  cluster.clearLayers();

  for (const t of items) {
    const loc = t.loc;
    if (!loc) continue;
    const { lat, lng: lon } = loc;
    if (!isFinite(lat) || !isFinite(lon)) continue;

    const icon = getIconFor(t.cache_type_code ?? undefined);
    const marker = L.marker([lat, lon], { icon });
    marker.bindPopup(renderTargetPopup(t), {
      closeButton: true,
      autoPan: true,
    });
    cluster.addLayer(marker);
  }

  if (!nearbyMode.value && map && items.length > 0) {
    const bounds = cluster.getBounds();
    if (bounds.isValid())
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
  }
}

watch(targets, (items) => plotTargets(items));

// --- Utils ---

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

onMounted(async () => {
  await loadLocation();
  await init();
});
</script>
