<template>
  <div
    class="flex items-center justify-center gap-2 text-sm text-gray-500 dark:text-gray-400"
  >
    <ArrowPathIcon class="w-4 h-4 animate-spin shrink-0" aria-hidden="true" />
    <span>{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
import { ArrowPathIcon } from "@heroicons/vue/24/outline";

defineProps<{
  label: string;
}>();
</script>
