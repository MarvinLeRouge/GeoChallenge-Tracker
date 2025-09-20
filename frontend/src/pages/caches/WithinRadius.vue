<template>
    <div class="absolute inset-0">
        <div class="absolute inset-0 z-0">
            <MapBase @ready="onMapReady" @click="onMapClick" />
        </div>

        <div class="absolute left-2 right-2 bottom-2 z-50 flex flex-col gap-2">
            <div class="rounded-lg bg-white/95 border p-2 shadow">
                <div class="flex items-center gap-2">
                    <button class="border rounded px-2 py-1" @click="picking = true">Choisir sur la carte</button>
                    <button class="border rounded px-2 py-1" @click="useMyPos">Ma position</button>
                    <input type="number" min="0.1" step="0.1" v-model.number="radiusKm"
                        class="border rounded px-2 py-1 w-28" />
                    <span>km</span>
                    <button class="ml-auto border rounded px-3 py-1" :disabled="!center || !radiusKm || loading"
                        @click="search">
                        {{ loading ? 'Recherche…' : 'Rechercher' }}
                    </button>
                </div>
                <p v-if="picking" class="text-xs text-indigo-700 mt-1">Cliquez sur la carte pour choisir le centre…</p>
                <p v-if="center" class="text-xs text-gray-600 mt-1">Centre: {{ center.lat.toFixed(5) }}, {{
                    center.lng.toFixed(5) }}</p>
            </div>

            <div v-if="count !== null" class="self-start rounded bg-white/95 border px-2 py-1 text-sm">
                {{ count }} cache(s)
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import L from 'leaflet'
import MapBase from '@/components/map/MapBase.vue'
import api from '@/api/http'
import 'leaflet.markercluster'
import { getIconFor } from '@/config/cache-icon'

let map: L.Map | null = null
let circle: L.Circle | null = null
let results: L.LayerGroup | null = null
let cluster: L.MarkerClusterGroup | null = null

const center = ref<{ lat: number; lng: number } | null>(null)
const radiusKm = ref(10)
const picking = ref(false)
const loading = ref(false)
const count = ref<number | null>(null)


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
function useMyPos() {
    if (!map) return
    map.locate({ setView: true, maxZoom: 12 }).once('locationfound', (e: any) => setCenter(e.latlng))
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
        const { data } = await api.get('/caches/within-radius', { params: { lat, lon: lng, radius_km: radiusKm.value } })
        results?.clearLayers()

        console.log("data", data)
        if (data?.type === 'FeatureCollection') {
            // GeoJSON
            L.geoJSON(data, {
                pointToLayer: (feat, latlng) => L.marker(latlng, { icon: getIconFor(feat?.properties?.type) }),
            }).eachLayer((lyr) => cluster!.addLayer(lyr))
            count.value = data.features?.length ?? 0
        } else if (Array.isArray(data?.items)) {
            data.items.forEach((c: any) => {
                console.log(c)
                const lat = c.lat ?? c.latitude, lon = c.lon ?? c.longitude
                if (isFinite(lat) && isFinite(lon)) {
                    cluster!.addLayer(L.marker([lat, lon], { icon: getIconFor(c.type) }))
                }
            })
            count.value = data.total
        } else {
            count.value = 0
        }
        drawCircle()
    } finally { loading.value = false }
}
</script>