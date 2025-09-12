<template>
    <section class="max-w-screen-md mx-auto text-center space-y-6">
      <div class="inline-flex items-center justify-center rounded-2xl border p-6 bg-gray-50">
        <WrenchScrewdriverIcon class="w-12 h-12 text-gray-500" aria-hidden="true" />
      </div>
  
      <h1 class="text-2xl font-bold">{{ title }}</h1>
      <p class="text-gray-600">
        {{ message }}
      </p>
  
      <div class="flex items-center justify-center gap-3">
        <RouterLink to="/" class="border rounded px-4 py-2 hover:bg-gray-50">Accueil</RouterLink>
        <RouterLink v-if="helpTo" :to="helpTo" class="border rounded px-4 py-2 hover:bg-gray-50">Aide</RouterLink>
        <slot name="actions" />
      </div>
  
      <p v-if="hint" class="text-xs text-gray-500">{{ hint }}</p>
    </section>
  </template>
  
  <script setup lang="ts">
  import { WrenchScrewdriverIcon } from '@heroicons/vue/24/outline'
  
  defineProps<{
    title?: string
    message?: string
    helpTo?: string
    hint?: string
  }>()
  </script>
  