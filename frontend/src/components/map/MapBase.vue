<template>
    <!-- le parent de MapBase doit être positionné (relative/absolute) ; ici on remplit -->
    <div ref="el" class="absolute inset-0"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, watch, defineEmits, defineExpose } from "vue";
import L from 'leaflet'
import { installCrosshairPicker, type CrosshairPicker } from "./crosshairPicker";
import { useAuthStore } from '@/store/auth'

type LatLng = [number, number] // [lat, lng]
const props = defineProps<{ center?: LatLng; zoom?: number; attribution?: string }>()

const emit = defineEmits<{
    (e: "ready", map: L.Map): void;
    (e: "pick", payload: { lat: number; lng: number }): void;
}>();
const el = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let picker: CrosshairPicker | null = null;
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

// --- listener resize défini au niveau module pour pouvoir le retirer proprement ---
const onResize = () => map?.invalidateSize(true);

function init() {
    if (!el.value) return;
    map = L.map(el.value, { zoomControl: true });
    L.tileLayer(tileUrl(), { maxZoom: 19, attribution: attribution.value }).addTo(map);
    map.setView(currentCenter(), initialZoom.value);
    // (si tu n’en as pas besoin, tu peux retirer cet emit de click)
    // map.on("click", (ev) => emit("click" as any, ev));

    emit("ready", map);              // ✅ on garde CE emit
    setTimeout(() => map?.invalidateSize(true), 0);
}

onMounted(() => {
    init()
    window.addEventListener("resize", onResize);

    // Crosshair picker installé mais inactif tant qu’on ne l’active pas
    if (map) {
        picker = installCrosshairPicker(map, (ll) => {
            emit("pick", { lat: ll.lat, lng: ll.lng });
        });
    }


    onBeforeUnmount(() => window.removeEventListener('resize', onResize))
    // ➕ Ajout non intrusif du picker (désactivé par défaut)
})

// si le profil arrive après coup, on recadre UNE fois
let recentered = false
watch(() => auth.user, (u) => {
    if (!map || recentered || props.center) return
    const c = getUserCenter()
    if (c) { map.setView(c, initialZoom.value); recentered = true }
}, { immediate: true })

onBeforeUnmount(() => {
    window.removeEventListener("resize", onResize);
    if (picker) picker.destroy();
    if (map) {
        map.remove();
        map = null;
    }
});

// ➕ Exposer des méthodes au parent (pour déclencher depuis un bouton)
function enablePick() {
    console.log("[MapBase] enablePick()");
    console.log("[MapBase] picker is", picker);

    picker?.enable();
}
function disablePick() {
    console.log("[MapBase] disablePick()");
    picker?.disable();
}
defineExpose({ getMap: () => map, enablePick, disablePick });

</script>