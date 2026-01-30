<!-- src/pages/userChallenges/Details.vue -->
<template>
  <div class="p-4 space-y-4">
    <button
      class="inline-flex items-center gap-2 text-sm"
      @click="router.back()"
    >
      <ArrowLeftIcon class="w-5 h-5" /> Retour
    </button>

    <div
      v-if="loading"
      class="text-center text-gray-500"
    >
      Chargement…
    </div>
    <div
      v-if="error"
      class="text-center text-red-600 text-sm"
    >
      {{ error }}
    </div>

    <div
      v-if="uc"
      class="space-y-4"
    >
      <!-- En-tête -->
      <div class="rounded-lg border bg-white p-4 shadow-sm">
        <div class="flex justify-between items-start gap-3">
          <div class="min-w-0">
            <h1 class="font-semibold text-lg break-words">
              {{ uc.challenge.name }}
            </h1>
            <p class="text-sm text-gray-500">
              GC: {{ uc.cache.GC }}
            </p>
            <p class="text-xs text-gray-400">
              Créé: {{ new Date(uc.created_at).toLocaleDateString() }} · Màj:
              {{ new Date(uc.updated_at).toLocaleDateString() }}
            </p>
            <p class="text-sm mt-1">
              Statut: <span class="font-medium">{{ uc.status }}</span>
              <span
                v-if="uc.computed_status"
                class="text-gray-500"
              > (computed: {{ uc.computed_status
              }})</span>
              <span class="text-gray-500"> → effective: {{ uc.effective_status }}</span>
            </p>
          </div>
          <InformationCircleIcon class="w-6 h-6 text-gray-500 shrink-0" />
        </div>

        <!-- Progress -->
        <div class="mt-3">
          <div
            v-if="uc.progress && uc.progress.percent !== null"
            class="w-full bg-gray-200 rounded h-2"
          >
            <div
              class="bg-green-500 h-2 rounded"
              :style="{ width: uc.progress.percent + '%' }"
            />
          </div>
          <p
            v-else
            class="text-xs text-gray-400"
          >
            Pas encore commencé
          </p>
        </div>

        <!-- Actions statut -->
        <div class="flex gap-2 mt-3">
          <button
            v-if="canAccept"
            class="p-2 rounded-full border bg-white hover:bg-green-50 disabled:opacity-50"
            :disabled="loading"
            title="Accepter"
            @click="patchStatus('accepted')"
          >
            <CheckIcon class="w-5 h-5" />
          </button>
          <button
            v-if="canDismiss"
            class="p-2 rounded-full border bg-white hover:bg-red-50 disabled:opacity-50"
            :disabled="loading"
            title="Refuser"
            @click="patchStatus('dismissed')"
          >
            <XMarkIcon class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Description du challenge -->
      <div class="rounded-lg border bg-white p-4 shadow-sm">
        <h2 class="font-semibold mb-2">
          Description
        </h2>
        <!-- Rendu HTML sanitisé -->
        <div
          class="prose prose-sm max-w-none"
          v-html="safeDescription"
        />
      </div>

      <!-- Notes & override -->
      <div class="rounded-lg border bg-white p-4 shadow-sm space-y-3">
        <h2 class="font-semibold">
          Notes
        </h2>
        <textarea
          v-model="notes"
          rows="3"
          class="w-full border rounded px-3 py-2"
          placeholder="Ajouter une note…"
        />
        <div class="text-sm text-gray-600">
          <label class="block mb-1 font-medium">Raison d’override (optionnel)</label>
          <input
            v-model="overrideReason"
            type="text"
            class="w-full border rounded px-3 py-2"
            placeholder="Ex: contrôle manuel…"
          >
        </div>
        <div class="flex gap-2">
          <button
            class="px-3 py-2 rounded border bg-white hover:bg-gray-50 disabled:opacity-50"
            :disabled="loading"
            @click="saveNotes"
          >
            Enregistrer
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserChallenge } from '@/composables/useUserChallenge'
import api from '@/api/http'
import DOMPurify from 'dompurify'

import {
    ArrowLeftIcon,
    CheckIcon,
    XMarkIcon,
    InformationCircleIcon,
} from '@heroicons/vue/24/outline'

type Progress = {
    percent: number | null
    tasks_done: number | null
    tasks_total: number | null
    checked_at: string | null
}
type Detail = {
    id: string
    status: 'pending' | 'accepted' | 'dismissed' | 'completed'
    computed_status: 'pending' | 'accepted' | 'dismissed' | 'completed' | null
    effective_status: 'pending' | 'accepted' | 'dismissed' | 'completed'
    progress: Progress | null
    updated_at: string
    created_at: string
    manual_override: boolean
    override_reason: string | null
    notes: string | null
    challenge: { id: string; name: string; description?: string | null }
    cache: { id: string; GC: string }
}

const route = useRoute()
const router = useRouter()
const id = route.params.id as string
const { uc, loadingDetail: loading, errorDetail: error, safeDescription, fetchDetail } =
  useUserChallenge(id)

const notes = ref('')
const overrideReason = ref('')

const canAct = computed(() => uc.value && uc.value.computed_status !== 'completed')
const canAccept = computed(() =>
    uc.value && !['accepted', 'completed'].includes(uc.value.status) && uc.value.computed_status !== 'completed'
)
const canDismiss = computed(() =>
    uc.value && !['dismissed', 'completed'].includes(uc.value.status) && uc.value.computed_status !== 'completed'
)

async function patchStatus(status: Detail['status']) {
    if (!uc.value) return
    loading.value = true
    try {
        await api.patch(`/my/challenges/${uc.value.id}`, { status })
        await fetchDetail()
    } catch (e: any) {
        error.value = e?.message ?? 'Erreur de mise à jour'
    } finally {
        loading.value = false
    }
}

async function saveNotes() {
    if (!uc.value) return
    loading.value = true
    try {
        await api.patch(`/my/challenges/${uc.value.id}`, {
            notes: notes.value || null,
            override_reason: overrideReason.value || null,
        })
        await fetchDetail()
    } catch (e: any) {
        error.value = e?.message ?? 'Erreur enregistrement'
    } finally {
        loading.value = false
    }
}

onMounted(fetchDetail)
</script>
