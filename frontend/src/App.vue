<template>
  <AppShell />
  <BaseToast ref="toast" />
</template>

<script setup lang="ts">
import { ref, provide } from 'vue'
import AppShell from '@/app/AppShell.vue'
import BaseToast from '@/components/BaseToast.vue' // ⬅️ crée-le si pas fait

const toast = ref()
provide('toast', toast) // ⬅️ dispo partout via inject('toast')
</script>