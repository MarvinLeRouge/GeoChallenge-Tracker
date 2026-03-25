<template>
  <AppShell />
  <BaseToast ref="toast" />
</template>

<script setup lang="ts">
import { ref, provide, watch } from 'vue'
import AppShell from '@/app/AppShell.vue'
import BaseToast from '@/components/BaseToast.vue'
import { registerToast } from '@/utils/toastBus'

const toast = ref()
provide('toast', toast) // ⬅️ dispo partout via inject('toast')

// Expose showToast to the module-level bus so Axios interceptors can use it
watch(toast, (t) => { if (t?.showToast) registerToast((args) => t.showToast(args)) }, { immediate: true })
</script>