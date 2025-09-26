<template>
  <div class="absolute inset-0">
    <div class="absolute inset-0 z-0">
      <MapBase
        ref="mapRef"
        @ready="onMapReady"
        @click="onMapClick"
        @pick="onMapPick"
      />
    </div>

    <div class="absolute left-2 right-2 bottom-2 z-40 flex flex-col gap-2 with-fab">
      <div class="rounded-lg bg-white/95 border p-2 shadow">
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="border rounded px-3 py-3"
            aria-label="Choisir sur la carte"
            title="Choisir sur la carte"
            @click="startPick"
          >
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
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
                strokeWidth="2"
              />
            </svg>
          </button>
          <input
            v-model.number="radiusKm"
            type="number"
            min="0.1"
            step="0.1"
            class="border rounded px-2 py-1 w-20"
          >
          <span>km</span>
          <button
            type="button"
            class="border rounded px-3 py-3"
            aria-label="Rechercher"
            title="Rechercher"
            :disabled="!center || !radiusKm"
            @click="search"
          >
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              aria-hidden="true"
            >
              <path
                d="M10 2a8 8 0 105.293 14.293l3.707 3.707 1.414-1.414-3.707-3.707A8 8 0 0010 2zm0 2a6 6 0 110 12A6 6 0 0110 4z"
              />
            </svg>
          </button>
        </div>
        <p
          v-if="picking"
          class="text-xs text-indigo-700 mt-1"
        >
          Cliquez sur la carte pour choisir le centre…
        </p>
        <p
          v-if="center"
          class="text-xs text-gray-600 mt-1"
        >
          Centre: {{ centerDM }}<span v-if="count !== null"> — {{ count }} cache(s)</span>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import L from 'leaflet'
import MapBase from '@/components/map/MapBase.vue'
import api from '@/api/http'
import 'leaflet.markercluster'
import { getIconFor } from '@/config/cache-icon'
import type { ApiListResponse, CacheCompact } from '@/types/caches'

let map: L.Map | null = null
let circle: L.Circle | null = null
let results: L.LayerGroup | null = null
let cluster: L.MarkerClusterGroup | null = null

const center = ref<{ lat: number; lng: number } | null>(null)
const radiusKm = ref(10)
const picking = ref(false)
const loading = ref(false)
const count = ref<number | null>(null)
const mapRef = ref<InstanceType<typeof MapBase> | null>(null);

function startPick() {
    console.log("[parent] startPick clicked");
    const inst = mapRef.value;
    console.log("[parent] inst =", inst);
    console.log("[parent] enablePick type =", typeof inst?.enablePick);
    if (typeof inst?.enablePick === "function") {
        inst.enablePick();       // active le mode pick côté MapBase (curseur/réticule)
        picking.value = true;    // on garde ta logique existante pour onMapClick
    } else {
        console.warn("[parent] enablePick NOT found on MapBase instance");
    }
}

function onMapPick(p: { lat: number; lng: number }) {
    picking.value = false;                 // on sort du mode sélection
    setCenter(L.latLng(p.lat, p.lng));     // réutilise ta logique existante
}


function onMapReady(m: L.Map) {
    map = m
    cluster = L.markerClusterGroup({
        showCoverageOnHover: false,
        spiderfyOnMaxZoom: true,
        disableClusteringAtZoom: 15,
        maxClusterRadius: 60,
    }).addTo(map)
}
function onMapClick(e: L.LeafletMouseEvent) {
    if (!picking.value) return
    picking.value = false
    setCenter(e.latlng)
}
function setCenter(latlng: L.LatLng) {
    center.value = { lat: latlng.lat, lng: latlng.lng }
    drawCircle()
}
function drawCircle() {
    if (!map || !center.value) return
    circle?.remove()
    circle = L.circle(center.value, { radius: radiusKm.value * 1000, color: '#2563eb' }).addTo(map)
}
watch(radiusKm, () => drawCircle())

async function search() {
    if (!center.value) return
    loading.value = true; count.value = null
    try {
        const { lat, lng } = center.value
        const { data } = await api.get<ApiListResponse<CacheCompact>>('/caches/within-radius', { params: { lat, lon: lng, radius_km: radiusKm.value } })
        results?.clearLayers()

        if (Array.isArray(data?.items)) {
            data.items.forEach((c: CacheCompact) => {
                const lat = c.lat ?? c.latitude, lon = c.lon ?? c.longitude
                if (isFinite(lat) && isFinite(lon)) {
                    cluster!.addLayer(L.marker([lat, lon], { icon: getIconFor(c.type.code) }))
                }
            })
            count.value = typeof data.total === 'number' ? data.total : (Array.isArray(data.items) ? data.items.length : 0)
        } else {
            count.value = 0
        }
        drawCircle()
    } finally { loading.value = false }
}

function formatDM(value: number, isLat: boolean): string {
    const hemi = isLat ? (value >= 0 ? "N" : "S") : (value >= 0 ? "E" : "W");
    const abs = Math.abs(value);
    const deg = Math.floor(abs);
    const min = (abs - deg) * 60;
    // lat: 2 chiffres, lon: 3 chiffres (padding)
    const pad = (n: number, w: number) => n.toString().padStart(w, "0");
    const degStr = pad(deg, isLat ? 2 : 3);
    // mm.xyz' → 3 décimales
    const minStr = min.toFixed(3).padStart(6, "0"); // ex: "05.123"
    return `${hemi} ${degStr}° ${minStr}'`;
}

const centerDM = computed(() => {
    if (!center.value) return "";
    return `${formatDM(center.value.lat, true)} ${formatDM(center.value.lng, false)}`;
});

</script>