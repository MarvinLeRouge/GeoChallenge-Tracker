<template>
  <section>
    <h2 class="text-xl font-semibold">Zone protégée</h2>
    <pre class="text-xs">{{ user }}</pre>
  </section>
</template>
<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/store/auth'
const { user } = storeToRefs(useAuthStore())
</script>
