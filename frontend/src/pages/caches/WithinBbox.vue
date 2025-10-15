<template>
    <div class="absolute inset-0">
        <div class="absolute inset-0 z-0">
            <MapBase ref="mapRef" @ready="onMapReady" @pick="onMapPick" />
        </div>

        <div class="absolute left-2 right-2 bottom-2 z-40 flex flex-col gap-2 with-fab">
            <div class="rounded-lg bg-white/95 border p-2 shadow">
                <div class="flex items-center gap-2">
                    <button type="button" class="border rounded px-3 py-3" aria-label="Choisir sur la carte"
                        title="Choisir sur la carte" @click="startPick">
                        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                            <path
                                d="M11 2v3a1 1 0 002 0V2h-2zm0 17v3h2v-3a1 1 0 10-2 0zM2 11h3a1 1 0 100-2H2v2zm17 0h3v-2h-3a1 1 0 100 2z" />
                            <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="2" />
                        </svg>
                    </button>
                    <button type="button"
                        class="relative border rounded px-3 py-3 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition"
                        :disabled="isDisabled" @click="search" :title="searchTitle" :aria-label="searchTitle">
                        <!-- Icône principale -->
                        <ArrowPathIcon v-if="loading" class="w-5 h-5 animate-spin" aria-hidden="true" />
                        <NoSymbolIcon v-else-if="isDisabled" class="w-5 h-5" aria-hidden="true" />
                        <MagnifyingGlassIcon v-else class="w-5 h-5" aria-hidden="true" />

                        <!-- Badge d’état (facultatif) -->
                        <span v-if="!loading && hasMore && currentPage > 1"
                            class="absolute -right-1 -bottom-1 grid place-items-center w-4 h-4 bg-white border rounded-full"
                            aria-hidden="true">
                            <PlusIcon class="w-3 h-3" />
                        </span>
                        <span v-else-if="!loading && !hasMore"
                            class="absolute -right-1 -bottom-1 grid place-items-center w-4 h-4 bg-white border rounded-full"
                            aria-hidden="true">
                            <CheckIcon class="w-3 h-3" />
                        </span>
                    </button>
                </div>
                <p v-if="bbox" class="text-xs text-gray-600 mt-1">
                    BBox: {{ bboxDM }}<span v-if="count !== null"> — {{ count }} cache(s)</span>
                </p>
                <p v-else-if="picking !== 'idle'" class="text-xs text-indigo-700 mt-1">
                    Cliquez une première fois pour le coin A, déplacez le réticule, puis cliquez pour le coin B…
                </p>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import L from 'leaflet'
import MapBase from '@/components/map/MapBase.vue'
import api from '@/api/http'
import 'leaflet.markercluster'
import { getIconFor } from '@/config/cache-icon'
import type { ApiListResponse, CacheCompact } from '@/types/caches'
import {
    MagnifyingGlassIcon,
    NoSymbolIcon,
    ArrowPathIcon,
    PlusIcon,
    CheckIcon,
} from '@heroicons/vue/24/solid'

let map: L.Map | null = null
let moveHandler: ((e: L.LeafletMouseEvent) => void) | null = null
let rect: L.Rectangle | null = null
let results: L.LayerGroup | null = null
let cluster: L.MarkerClusterGroup | null = null

type Pt = { lat: number; lng: number }
const cornerA = ref<Pt | null>(null)
const cornerB = ref<Pt | null>(null)
const picking = ref<"idle" | "first" | "second">("idle")
const bbox = ref<[number, number, number, number] | null>(null) // [minLat, minLng, maxLat, maxLng]
const loading = ref(false)
const count = ref<number | null>(null)
const mapRef = ref<InstanceType<typeof MapBase> | null>(null);
const hasBbox = computed(() => bbox.value !== null && Array.isArray(bbox.value) && bbox.value.length === 4);
// Pagination & dédup (AJOUT)
const currentPage = ref(1)
const nbPages = ref(1)
const pageSize = ref(100)
const seenIds = ref(new Set<string>())
const hasMore = computed(() => currentPage.value <= nbPages.value)

const isDisabled = computed(() =>
    loading.value || !hasBbox.value || !hasMore.value
)

const searchTitle = computed(() => {
    if (loading.value) return 'Chargement…'
    if (!hasBbox.value) return 'Définir une zone de recherche'
    if (!hasMore.value) return 'Fin de liste'
    return currentPage.value > 1 ? 'Charger la suite' : 'Rechercher'
})

function startPick() {
    console.log("[parent] startPick clicked");
    if (!map) return
    // reset précédente sélection
    cornerA.value = null
    cornerB.value = null
    bbox.value = null
    rect?.remove(); rect = null
    picking.value = "first"
    mapRef.value?.enablePick()
}

function onMapPick(p: { lat: number; lng: number }) {
    if (!map) return

    if (picking.value === "first") {
        currentPage.value = 1
        nbPages.value = 1
        seenIds.value.clear()
        cluster?.clearLayers()

        cornerA.value = { lat: p.lat, lng: p.lng }

        // handler d’aperçu: coin A -> position curseur
        moveHandler = (e: L.LeafletMouseEvent) => {
            drawPreviewRect(cornerA.value!, e.latlng)
            updateBboxFromCorners(cornerA.value!, e.latlng)
        }
        map.on("mousemove", moveHandler)

        // on attend le 2e clic
        picking.value = "second"
        mapRef.value?.enablePick()
        return
    }

    if (picking.value === "second") {
        cornerB.value = { lat: p.lat, lng: p.lng }
        // finalise le rectangle & la bbox
        if (moveHandler) { map.off("mousemove", moveHandler); moveHandler = null }
        drawPreviewRect(cornerA.value!, cornerB.value!)
        updateBboxFromCorners(cornerA.value!, cornerB.value!)
        picking.value = "idle"
    }
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

async function search() {
    if (!hasBbox.value) return
    loading.value = true; count.value = null
    try {
        const [south, west, north, east] = bbox.value!
        const page = currentPage.value
        const { data } = await api.get<ApiListResponse<CacheCompact>>('/caches/within-bbox', {
            params: {
                page,
                min_lat: south,
                min_lon: west,
                max_lat: north,
                max_lon: east,
            },
        });
        if ((data as any)?.page !== undefined) {
            currentPage.value = (data as any).page + 1
        }
        if ((data as any)?.nb_pages !== undefined) {
            nbPages.value = (data as any).nb_pages
        }
        if ((data as any)?.page_size !== undefined) {
            pageSize.value = (data as any).page_size
        }
        results?.clearLayers()

        if (Array.isArray(data?.items)) {
            // AJOUT: filtrer les nouveaux items par _id
            const fresh = Array.isArray((data as any)?.items)
                ? (data as any).items.filter((c: any) => {
                    const id = c?._id
                    if (!id) return false
                    if (seenIds.value.has(id)) return false
                    seenIds.value.add(id)
                    return true
                })
                : []
            fresh.forEach((c: CacheCompact) => {
                const lat = c.lat ?? c.latitude, lon = c.lon ?? c.longitude
                if (isFinite(lat) && isFinite(lon)) {
                    cluster!.addLayer(L.marker([lat, lon], { icon: getIconFor(c.type.code) }))
                }
            })
            count.value = typeof data.total === 'number' ? data.total : (Array.isArray(data.items) ? data.items.length : 0)
        } else {
            count.value = 0
        }
    } finally {
        loading.value = false
    }
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

const bboxDM = computed(() => {
    if (!bbox.value) return ""
    const [s, w, n, e] = bbox.value
    return `${formatDM(s, true)} ${formatDM(w, false)} → ${formatDM(n, true)} ${formatDM(e, false)}`
})

function cornersToBounds(a: Pt, b: Pt): L.LatLngBoundsExpression {
    const south = Math.min(a.lat, b.lat)
    const north = Math.max(a.lat, b.lat)
    const west = Math.min(a.lng, b.lng)
    const east = Math.max(a.lng, b.lng)
    return [[south, west], [north, east]]
}

function drawPreviewRect(a: Pt, b: Pt) {
    const bounds = cornersToBounds(a, b)
    if (!rect) {
        rect = L.rectangle(bounds, { color: "#2563eb", weight: 2, fillOpacity: 0.05 })
            .addTo(map!)
    } else {
        rect.setBounds(bounds)
    }
}

function updateBboxFromCorners(a: Pt, b: Pt) {
    const s = Math.min(a.lat, b.lat)
    const n = Math.max(a.lat, b.lat)
    const w = Math.min(a.lng, b.lng)
    const e = Math.max(a.lng, b.lng)
    bbox.value = [s, w, n, e]
}

</script>