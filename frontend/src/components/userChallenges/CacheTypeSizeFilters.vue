<template>
  <div
    class="rounded-lg border bg-white p-4 shadow-xs dark:bg-gray-800 dark:border-gray-700"
  >
    <h2 class="font-semibold mb-3">Filtres</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label
          class="block text-sm font-medium text-gray-700 mb-1 dark:text-gray-300"
          >Type de cache</label
        >
        <select
          :value="selectedCacheType"
          class="w-full border rounded-sm px-3 py-2 bg-white dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
          @change="onTypeChange"
        >
          <option value="">Tous les types</option>
          <option
            v-for="type in sortedCacheTypes"
            :key="type._id"
            :value="type.code"
          >
            {{ type.name }} ({{ type.code }})
          </option>
        </select>
      </div>

      <div>
        <label
          class="block text-sm font-medium text-gray-700 mb-1 dark:text-gray-300"
          >Taille de cache</label
        >
        <select
          :value="selectedCacheSize"
          class="w-full border rounded-sm px-3 py-2 bg-white dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
          @change="onSizeChange"
        >
          <option value="">Toutes les tailles</option>
          <option
            v-for="size in sortedCacheSizes"
            :key="size._id"
            :value="size.code"
          >
            {{ size.name }} ({{ size.code }})
          </option>
        </select>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { CacheType, CacheSize } from "@/types/challenges";

defineProps<{
  selectedCacheType: string;
  selectedCacheSize: string;
  sortedCacheTypes: CacheType[];
  sortedCacheSizes: CacheSize[];
}>();

const emit = defineEmits<{
  "update:selectedCacheType": [value: string];
  "update:selectedCacheSize": [value: string];
  change: [];
}>();

// Reads the native string value directly (not Vue's v-model _value lookup):
// assumes string-valued options, true for CacheType.code/CacheSize.code.
function onTypeChange(event: Event) {
  emit("update:selectedCacheType", (event.target as HTMLSelectElement).value);
  emit("change");
}

function onSizeChange(event: Event) {
  emit("update:selectedCacheSize", (event.target as HTMLSelectElement).value);
  emit("change");
}
</script>
