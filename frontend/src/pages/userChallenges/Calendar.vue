<template>
  <div class="p-4 space-y-4">
    <!-- En-tête -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">Calendar Challenge</h1>
        <p class="text-gray-600 dark:text-gray-400">
          Vérification de completion des 365/366 jours de l'année
        </p>
      </div>
    </div>

    <!-- Filtres -->
    <CacheTypeSizeFilters
      v-model:selected-cache-type="selectedCacheType"
      v-model:selected-cache-size="selectedCacheSize"
      :sorted-cache-types="sortedCacheTypes"
      :sorted-cache-sizes="sortedCacheSizes"
      @change="fetchCalendar"
    />

    <!-- Loading/Error -->
    <div v-if="loading" class="py-8">
      <LoadingIndicator label="Chargement du calendrier…" />
    </div>
    <div
      v-if="error"
      class="text-center text-red-600 text-sm py-4 bg-red-50 rounded-lg dark:text-red-400 dark:bg-red-950"
    >
      {{ error }}
    </div>

    <!-- Résultats Calendar -->
    <div v-if="calendarResult && !loading" class="space-y-4">
      <!-- Statistiques -->
      <div
        class="rounded-lg border bg-white p-4 shadow-xs dark:bg-gray-800 dark:border-gray-700"
      >
        <h2 class="font-semibold mb-3">Résumé</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="bg-green-50 p-3 rounded-lg dark:bg-green-950">
            <div class="flex items-center gap-2">
              <CheckCircleIcon
                class="h-6 w-6 text-green-600 shrink-0 dark:text-green-400"
                aria-hidden="true"
              />
              <div>
                <div
                  class="text-2xl font-bold text-green-800 dark:text-green-300"
                >
                  {{ calendarResult.completed_days.length }}
                </div>
                <div class="text-sm text-green-700 dark:text-green-400">
                  Jours complétés
                </div>
              </div>
            </div>
          </div>
          <div class="bg-blue-50 p-3 rounded-lg dark:bg-blue-950">
            <div class="flex items-center gap-2">
              <CalendarIcon
                class="h-6 w-6 text-blue-600 shrink-0 dark:text-blue-400"
                aria-hidden="true"
              />
              <div>
                <div
                  class="text-2xl font-bold text-blue-800 dark:text-blue-300"
                >
                  {{ (calendarResult.completion_rate_365 * 100).toFixed(1) }}%
                </div>
                <div class="text-sm text-blue-600 dark:text-blue-400">
                  Completion 365 jours
                </div>
              </div>
            </div>
          </div>
          <div class="bg-purple-50 p-3 rounded-lg dark:bg-purple-950">
            <div class="flex items-center gap-2">
              <CalendarIcon
                class="h-6 w-6 text-purple-600 shrink-0 dark:text-purple-400"
                aria-hidden="true"
              />
              <div>
                <div
                  class="text-2xl font-bold text-purple-800 dark:text-purple-300"
                >
                  {{ (calendarResult.completion_rate_366 * 100).toFixed(1) }}%
                </div>
                <div class="text-sm text-purple-600 dark:text-purple-400">
                  Completion 366 jours (bissextile)
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Calendrier visuel -->
      <div
        class="rounded-lg border bg-white p-4 shadow-xs dark:bg-gray-800 dark:border-gray-700"
      >
        <h2 class="font-semibold mb-3">Calendrier annuel</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <div
            v-for="month in 12"
            :key="month"
            class="border rounded-lg p-2 dark:border-gray-700"
          >
            <h3 class="text-sm font-medium text-center mb-2">
              {{ monthNames[month - 1] }}
            </h3>
            <div class="grid grid-cols-7 gap-1 text-xs">
              <!-- Jours du mois -->
              <button
                v-for="day in getDaysInMonth(month)"
                :key="`${month}-${day}`"
                type="button"
                class="w-6 h-6 flex items-center justify-center rounded-sm text-xs cursor-pointer focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-blue-500"
                :class="[
                  getDayClass(month, day),
                  isSelectedDay(month, day)
                    ? 'ring-2 ring-blue-500 ring-offset-1 dark:ring-offset-gray-800'
                    : '',
                ]"
                :title="getDayTitle(month, day)"
                :aria-label="getDayTitle(month, day)"
                :aria-pressed="isSelectedDay(month, day)"
                @click="selectDay(month, day)"
              >
                {{ day }}
              </button>
            </div>
            <!-- Détail du jour sélectionné -->
            <div
              v-if="selectedDay && selectedDay.month === month"
              class="mt-1 text-xs text-gray-700 bg-gray-200 rounded-sm px-2 py-1 dark:text-gray-300 dark:bg-gray-900"
            >
              {{ getDayTitle(selectedDay.month, selectedDay.day) }}
            </div>
            <!-- Jours manquants ce mois -->
            <div
              v-if="getMissingDaysCount(month) > 0"
              class="text-xs text-red-600 mt-1 dark:text-red-400"
            >
              {{ getMissingDaysCount(month) }} jour{{
                getMissingDaysCount(month) > 1 ? "s" : ""
              }}
              manquant{{ getMissingDaysCount(month) > 1 ? "s" : "" }}
            </div>
          </div>
        </div>

        <!-- Légende -->
        <div class="mt-4 flex flex-wrap gap-4 text-xs">
          <div class="flex items-center gap-1">
            <div class="w-4 h-4 bg-green-200 rounded-sm dark:bg-green-900" />
            <span>Jour complété</span>
          </div>
          <div class="flex items-center gap-1">
            <div class="w-4 h-4 bg-red-200 rounded-sm dark:bg-red-900" />
            <span>Jour manquant</span>
          </div>
          <div class="flex items-center gap-1">
            <div class="w-4 h-4 bg-gray-100 rounded-sm dark:bg-gray-700" />
            <span>Jour sans cache</span>
          </div>
        </div>
      </div>

      <!-- Statistiques détaillées par mois -->
      <div
        class="rounded-lg border bg-white p-4 shadow-xs dark:bg-gray-800 dark:border-gray-700"
      >
        <h2 class="font-semibold mb-3">Détails par mois</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="month in 12"
            :key="month"
            class="border rounded-lg p-3 dark:border-gray-700"
          >
            <h3 class="font-medium">
              {{ monthNames[month - 1] }}
            </h3>
            <div class="mt-2 space-y-1 text-sm">
              <div class="flex justify-between">
                <span>Complétés:</span>
                <span class="text-green-600 font-medium dark:text-green-400">
                  {{ getCompletedDaysInMonth(month) }}/{{
                    getDaysInMonth(month)
                  }}
                </span>
              </div>
              <div class="flex justify-between">
                <span>Manquants:</span>
                <span class="text-red-600 font-medium dark:text-red-400">
                  {{ getMissingDaysCount(month) }}
                </span>
              </div>
              <div class="flex justify-between">
                <span>Taux:</span>
                <span class="font-medium">
                  {{
                    (
                      (getCompletedDaysInMonth(month) / getDaysInMonth(month)) *
                      100
                    ).toFixed(1)
                  }}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import api from "@/api/http";
import type { CalendarResult } from "@/types/challenges";
import { useCalendarData } from "@/composables/useCalendarData";
import { useCacheTypeSizeFilters } from "@/composables/useCacheTypeSizeFilters";
import { toast } from "vue-sonner";
import { CheckCircleIcon, CalendarIcon } from "@heroicons/vue/24/outline";
import LoadingIndicator from "@/components/ui/LoadingIndicator.vue";
import CacheTypeSizeFilters from "@/components/userChallenges/CacheTypeSizeFilters.vue";

const loading = ref(false);
const error = ref("");
const calendarResult = ref<CalendarResult | null>(null);
const selectedDay = ref<{ month: number; day: number } | null>(null);

// Use the shared composable for cache type/size filters
const {
  selectedCacheType,
  selectedCacheSize,
  sortedCacheTypes,
  sortedCacheSizes,
  fetchCacheTypes,
  fetchCacheSizes,
} = useCacheTypeSizeFilters(error);

// Use the new composable for calendar data processing
const { calendarData, monthNames, getDaysInMonth } =
  useCalendarData(calendarResult);

function getDayClass(month: number, day: number): string {
  const calendarDay = calendarData.value.months[month - 1]?.days[day - 1];
  if (!calendarDay)
    return "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400";

  if (calendarDay.isCompleted) {
    return "bg-green-200 text-green-800 dark:bg-green-900 dark:text-green-300";
  } else if (calendarDay.isMissing) {
    return "bg-red-200 text-red-800 dark:bg-red-900 dark:text-red-300";
  } else {
    return "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400";
  }
}

function isSelectedDay(month: number, day: number): boolean {
  return selectedDay.value?.month === month && selectedDay.value?.day === day;
}

function selectDay(month: number, day: number): void {
  selectedDay.value = isSelectedDay(month, day) ? null : { month, day };
}

function getDayTitle(month: number, day: number): string {
  const calendarDay = calendarData.value.months[month - 1]?.days[day - 1];
  const dateLabel = `${String(day).padStart(2, "0")}/${String(month).padStart(2, "0")}`;
  if (!calendarDay) return dateLabel;

  if (calendarDay.count > 0) {
    const count = calendarDay.count.toLocaleString("fr-FR");
    return `${dateLabel} - ${count} cache${calendarDay.count > 1 ? "s" : ""}`;
  } else if (calendarDay.isMissing) {
    return `${dateLabel} - Jour manquant`;
  } else {
    return dateLabel;
  }
}

function getMissingDaysCount(month: number): number {
  const calendarMonth = calendarData.value.months[month - 1];
  return calendarMonth ? calendarMonth.missingCount : 0;
}

function getCompletedDaysInMonth(month: number): number {
  const calendarMonth = calendarData.value.months[month - 1];
  return calendarMonth ? calendarMonth.completedCount : 0;
}

async function fetchCalendar() {
  loading.value = true;
  error.value = "";

  try {
    const params = new URLSearchParams();
    if (selectedCacheType.value) {
      params.append("cache_type", selectedCacheType.value);
    }
    if (selectedCacheSize.value) {
      params.append("cache_size", selectedCacheSize.value);
    }

    const response = await api.get(`/my/challenges/basics/calendar?${params}`);
    calendarResult.value = response.data;
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })
      ?.response?.data?.detail;
    const msg = e instanceof Error ? e.message : String(e);
    error.value = detail || msg || "Erreur lors du chargement du calendrier";
    toast.error("Erreur chargement calendrier", { description: error.value });
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await Promise.all([fetchCacheTypes(), fetchCacheSizes(), fetchCalendar()]);
});
</script>
