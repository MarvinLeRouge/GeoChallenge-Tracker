<template>
  <!-- le parent de MapBase doit être positionné (relative/absolute) ; ici on remplit -->
  <div
    ref="el"
    class="absolute inset-0"
  />
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

function currentCenter(): LatLng {
    if (props.center) return props.center
    const loc = auth.user?.location
    console.log("loc", loc)
    if (loc && Number.isFinite(loc.lat) && Number.isFinite(loc.lon)) {
        console.log("loc found", loc.lat, loc.lon)
        return [loc.lat, loc.lon]
    }
    return fallbackCenter
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

// remplace ta logique de watch/recenter par ceci :

let recentered = false

function tryRecenterOnce() {
    if (!map || recentered) return
    // priorité au prop center, sinon user.location, sinon rien
    const fromProp = props.center
    const fromUser = auth.user?.location
    const target =
        (fromProp && Number.isFinite(fromProp[0]) && Number.isFinite(fromProp[1]))
            ? fromProp
            : (fromUser && Number.isFinite(fromUser.lat) && Number.isFinite(fromUser.lon))
                ? [fromUser.lat, fromUser.lon] as [number, number]
                : null

    if (target) {
        map.setView(target, initialZoom.value)
        recentered = true
    }
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

    tryRecenterOnce()
})

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

// 👉 réagir si le center prop change (par ex. via une recherche)
watch(() => props.center, () => {
    // on autorise un re-center si c’est un center “externe”
    recentered = false
    tryRecenterOnce()
})

// 👉 réagir si la localisation utilisateur arrive/après-coup
watch(() => auth.user?.location, () => {
    // seulement si on n’a pas encore recadré via user
    tryRecenterOnce()
})
</script>