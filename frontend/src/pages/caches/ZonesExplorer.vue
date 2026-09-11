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
      <MapBase ref="mapRef" :zoom="6" @ready="onMapReady" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import MapBase from "@/components/map/MapBase.vue";
import LoadingIndicator from "@/components/ui/LoadingIndicator.vue";
import { useZones } from "@/composables/useZones";
import type { Country, ZoneListItem } from "@/types/zones";

// ── State ────────────────────────────────────────────────────────────────────

const mapRef = ref<InstanceType<typeof MapBase> | null>(null);
const { loading, fetchCountries, fetchZones } = useZones();

const level = ref<0 | 1 | 2>(0);
const selectedCountry = ref<string | null>(null);

const allCountries = ref<Country[]>([]);
const zonesLevel0 = ref<ZoneListItem[]>([]);

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

// ── Loading ──────────────────────────────────────────────────────────────────

async function loadWorld() {
  const [countries, zones] = await Promise.all([
    fetchCountries(),
    fetchZones(0),
  ]);
  allCountries.value = countries;
  zonesLevel0.value = zones;
}

onMounted(loadWorld);

// ── Drill-down (Country/Region rendering completed in Tasks 8-9) ───────────

function drillToCountry(code: string) {
  selectedCountry.value = code;
  level.value = 1;
}

async function onMapReady() {
  // Populated in Task 8 with the level-1 choropleth render.
  await fetchZones(1, selectedCountry.value ?? undefined, []);
}
</script>
