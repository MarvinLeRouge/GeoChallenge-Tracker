<template>
    <!-- le parent de MapBase doit être positionné (relative/absolute) ; ici on remplit -->
    <div ref="el" class="absolute inset-0"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import L from 'leaflet'
import { useAuthStore } from '@/store/auth'

type LatLng = [number, number] // [lat, lng]
const props = defineProps<{ center?: LatLng; zoom?: number; attribution?: string }>()

const emit = defineEmits<{ (e:'ready', map:L.Map):void; (e:'click', ev:L.LeafletMouseEvent):void }>()
const el = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
const auth = useAuthStore()

const fallbackCenter: LatLng = [46.6, 2.6]  // France approx
const initialZoom = computed(() => props.zoom ?? 6)
const attribution = computed(
    () => props.attribution ?? '© OpenStreetMap contributors'
)

function getUserCenter(): [number, number] | null {
    const u = auth.user
    if (!u) return null

    // 1) GeoJSON: { location: { coordinates: [lon, lat] } }
    const gc = u.location?.coordinates
    if (Array.isArray(gc) && Number.isFinite(gc[0]) && Number.isFinite(gc[1])) {
        return [gc[1], gc[0]]
    }

    // 2) { location: { lat, lon } }
    if (u.location && Number.isFinite(u.location.lat) && Number.isFinite(u.location.lon)) {
        return [u.location.lat, u.location.lon]
    }

    // 3) { lat, lon } (réponse /my/profile/location actuelle)
    if (Number.isFinite(u.lat) && Number.isFinite(u.lon)) {
        return [u.lat, u.lon]
    }

    // 4) coords: "lat, lon"
    if (typeof u.coords === 'string') {
        const m = u.coords.split(',').map(s => Number(s.trim()))
        if (m.length === 2 && Number.isFinite(m[0]) && Number.isFinite(m[1])) {
            return [m[0], m[1]]
        }
    }
    return null
}

function currentCenter(): LatLng {
    return props.center ?? getUserCenter() ?? fallbackCenter
}

function tileUrl() {
    const retina = L.Browser.retina ? '@2x' : ''
    return `/tiles/{z}/{x}/{y}${retina}.png`
}

function init() {
  if (!el.value) return
  map = L.map(el.value, { zoomControl: true })
  L.tileLayer(tileUrl(), { maxZoom: 19, attribution: attribution.value }).addTo(map)
  map.setView(currentCenter(), initialZoom.value)
  map.on('click', (ev) => emit('click', ev))
  emit('ready', map)               // <-- expose la carte
  setTimeout(() => map?.invalidateSize(true), 0)
}
defineExpose({ getMap: () => map }) // <-- accès alternatif
/*
function init() {
    if (!el.value) return
    map = L.map(el.value, { zoomControl: true })
    L.tileLayer(tileUrl(), { maxZoom: 19, attribution: attribution.value, crossOrigin: true }).addTo(map)
    map.setView(currentCenter(), initialZoom.value)
    // forcer le resize après montage
    setTimeout(() => map?.invalidateSize(true), 0)
}
*/
onMounted(() => {
    init()
    const onResize = () => map?.invalidateSize()
    window.addEventListener('resize', onResize)
    onBeforeUnmount(() => window.removeEventListener('resize', onResize))
})

// si le profil arrive après coup, on recadre UNE fois
let recentered = false
watch(() => auth.user, (u) => {
    if (!map || recentered || props.center) return
    const c = getUserCenter()
    console.log("c", c)
    if (c) { map.setView(c, initialZoom.value); recentered = true }
}, { immediate: true })
onBeforeUnmount(() => { map?.remove(); map = null })
</script>