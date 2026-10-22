// src/composables/useCacheTypeSizeFilters.ts
import { ref, computed, type Ref } from "vue";
import api from "@/api/http";
import { toast } from "vue-sonner";
import type { CacheType, CacheSize } from "@/types/challenges";

// Mutates the caller-supplied error ref on fetch failure; the caller must
// coordinate with any other code writing to the same ref (e.g. a page's own
// domain fetch sharing the same error display).
export function useCacheTypeSizeFilters(error: Ref<string>) {
  const cacheTypes = ref<CacheType[]>([]);
  const cacheSizes = ref<CacheSize[]>([]);
  const selectedCacheType = ref("");
  const selectedCacheSize = ref("");

  // Tri alphabétique des types de cache
  const sortedCacheTypes = computed(() => {
    return [...cacheTypes.value].sort((a, b) => a.name.localeCompare(b.name));
  });

  // Tri des tailles par ordre logique
  const sortedCacheSizes = computed(() => {
    const sizeOrder = ["Micro", "Small", "Regular", "Large", "Other"];
    return [...cacheSizes.value].sort((a, b) => {
      const aIndex = sizeOrder.indexOf(a.name);
      const bIndex = sizeOrder.indexOf(b.name);
      return aIndex - bIndex;
    });
  });

  async function fetchCacheTypes() {
    try {
      const response = await api.get("/cache_types");
      cacheTypes.value = response.data;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      error.value = `Erreur chargement types: ${msg}`;
      toast.error("Erreur chargement types", { description: msg });
    }
  }

  async function fetchCacheSizes() {
    try {
      const response = await api.get("/cache_sizes");
      cacheSizes.value = response.data;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      error.value = `Erreur chargement tailles: ${msg}`;
      toast.error("Erreur chargement tailles", { description: msg });
    }
  }

  return {
    cacheTypes,
    cacheSizes,
    selectedCacheType,
    selectedCacheSize,
    sortedCacheTypes,
    sortedCacheSizes,
    fetchCacheTypes,
    fetchCacheSizes,
  };
}
