<template>
  <transition name="fade">
    <div
      v-if="visible"
      class="fixed bottom-4 right-4 z-[9999] bg-gray-900 text-white rounded-lg shadow-lg px-4 py-3]"
      role="status"
      aria-live="polite"
    >
      <div class="flex items-start gap-3 py-3">
        <component
          :is="icon"
          v-if="icon"
          class="w-10 h-10 shrink-0"
        />
        <div class="min-w-0">
          <div
            class="font-medium leading-snug truncate toaster__title"
            :title="title"
          >
            {{ title }}
          </div>

          <!-- body (optionnel) -->
          <div
            v-if="body"
            class="text-sm mt-1 whitespace-pre-line break-words toaster__txt"
          >
            {{ body }}
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const visible = ref(false)
const title = ref<string>('')
const body = ref<string>('')        // lignes multiples supportées via whitespace-pre-line
const icon = ref<any>(null)
let timeout: number | null = null

type ToastArgs =
    | string
    | {
        title: string
        body?: string      // facultatif → si renseigné, affiché sous le titre (multiligne OK avec \n)
        icon?: any
        duration?: number  // ms
    }

/** API publique */
function showToast(args: ToastArgs, iconComp?: any, duration = 3000) {
    // rétro-compat: showToast('texte simple', Icon)
    if (typeof args === 'string') {
        title.value = args
        body.value = ''
        icon.value = iconComp ?? null
    } else {
        title.value = args.title ?? ''
        body.value = args.body ?? ''
        icon.value = args.icon ?? null
        duration = args.duration ?? duration
    }

    visible.value = true
    if (timeout) clearTimeout(timeout)
    timeout = window.setTimeout(() => (visible.value = false), duration)
}

defineExpose({ showToast })
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
    transition: opacity .25s
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0
}

.toaster__title {
    font-size: 1.5em;
}
</style>