<template>
  <section class="max-w-screen-md mx-auto space-y-6">
    <header class="space-y-1">
      <h1 class="text-xl font-semibold">
        Importer un fichier GPX/ZIP
      </h1>
      <p class="text-sm text-gray-600">
        Un seul fichier à la fois. ZIP accepté (les GPX qu’il contient seront traités).
      </p>
    </header>

    <!-- Form -->
    <form
      class="space-y-5"
      @submit.prevent="submit"
    >
      <!-- Fichier -->
      <div class="space-y-1">
        <label class="text-sm font-medium">Fichier</label>
        <input
          type="file"
          accept=".gpx,.zip"
          @change="onPick"
        >
        <p
          v-if="file"
          class="text-xs text-gray-500"
        >
          {{ file.name }} — {{ (file.size / 1024).toFixed(0) }} Ko
        </p>
      </div>

      <!-- Mode d'import -->
      <div class="space-y-1">
        <label class="text-sm font-medium">Mode d'import</label>
        <div class="grid grid-cols-[auto_1fr_auto_1fr] gap-x-3 gap-y-2 items-center">
          <input
            v-model="importMode"
            type="radio"
            id="mode-all"
            value="all"
            class="justify-self-start"
          >
          <label for="mode-all" class="text-sm">Toutes les caches</label>

          <input
            v-model="importMode"
            type="radio"
            id="mode-found"
            value="found"
            class="justify-self-start"
          >
          <label for="mode-found" class="text-sm">Caches trouvées</label>
        </div>
        <p class="text-xs text-gray-500">
          Sélectionnez le mode d'import : découvrir de nouvelles caches ou ajouter des caches trouvées par vous.
        </p>
      </div>

      <!-- Type de source GPX -->
      <div class="space-y-1">
        <label class="text-sm font-medium">Type de source GPX</label>
        <select
          v-model="sourceType"
          class="w-full border rounded px-3 py-2 text-sm"
        >
          <option value="auto">Détection automatique</option>
          <option value="cgeo">c:geo (export GPX)</option>
          <option value="pocket_query">Pocket Query</option>
        </select>
        <p class="text-xs text-gray-500">
          Choisissez le format du fichier GPX ou laissez "Détection automatique" pour laisser le système déterminer le format.
        </p>
      </div>

      <!-- Actions -->
      <div class="flex items-center gap-3">
        <button
          class="border rounded px-3 py-2"
          :disabled="!file || loading"
          type="submit"
        >
          {{ loading ? `Import… ${progress}%` : 'Importer' }}
        </button>

        <RouterLink
          class="underline text-sm"
          to="/my/challenges"
        >
          Mes challenges
        </RouterLink>
      </div>

      <p
        v-if="error"
        class="text-sm text-red-600"
      >
        {{ error }}
      </p>
    </form>

    <!-- Résultats import -->
    <div
      v-if="result"
      class="space-y-4"
    >
      <h2 class="text-lg font-semibold">
        Résumé d’import
      </h2>

      <div class="grid gap-4 sm:grid-cols-2">
        <div class="rounded border p-3">
          <h3 class="text-sm font-medium mb-2">
            Statistiques
          </h3>
          <dl class="text-sm grid grid-cols-2 gap-x-3 gap-y-1">
            <template
              v-for="(val, key) in result.summary"
              :key="key"
            >
              <dt class="text-gray-500 capitalize">
                {{ pretty(key) }}
              </dt>
              <dd>{{ val }}</dd>
            </template>
          </dl>
        </div>

        <div
          v-if="result.challenge_stats"
          class="rounded border p-3"
        >
          <h3 class="text-sm font-medium mb-2">
            Challenges détectés
          </h3>
          <dl class="text-sm grid grid-cols-2 gap-x-3 gap-y-1">
            <template
              v-for="(val, key) in result.challenge_stats"
              :key="key"
            >
              <dt class="text-gray-500 capitalize">
                {{ pretty(key) }}
              </dt>
              <dd>{{ val }}</dd>
            </template>
          </dl>
        </div>
      </div>
    </div>

    <!-- Résultats sync -->
    <div
      v-if="sync"
      class="space-y-2"
    >
      <h2 class="text-lg font-semibold">
        Synchronisation de vos challenges
      </h2>
      <div class="rounded border p-3">
        <pre class="text-xs overflow-auto">{{ sync }}</pre>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { toast } from 'vue-sonner'
import api from '@/api/http'
import type { ChallengeSyncStats, ImportResponse } from '@/types/challenges'
import { isAxiosError } from 'axios'

const file = ref<File | null>(null)
const importMode = ref<'all' | 'found'>('all')  // 'all' par défaut
const sourceType = ref<'auto' | 'cgeo' | 'pocket_query'>('auto')  // Valeur par défaut
const loading = ref(false)
const progress = ref(0)
const error = ref('')
const result = ref<ImportResponse | null>(null)
const sync = ref<ChallengeSyncStats | null>(null)

function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  file.value = input.files && input.files[0] ? input.files[0] : null
}

function pretty(k: string) {
  return k.replaceAll('_', ' ')
}

async function submit() {
  if (!file.value) return
  loading.value = true
  progress.value = 0
  error.value = ''
  result.value = null
  sync.value = null

  try {
    const fd = new FormData()
    fd.append('file', file.value)

    // Import - use importMode and sourceType
    const { data } = await api.post<ImportResponse>('/caches/upload-gpx', fd, {
      params: {
        import_mode: importMode.value,
        source_type: sourceType.value
      },
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (p) => {
        if (p.total) {
          // Only update progress if no error has occurred
          if (!error.value) {
            progress.value = Math.round((p.loaded / p.total) * 100)
          }
        }
      }
    })

    result.value = data
    toast.success('GPX importé', { description: 'Vos données ont été mises à jour.' })

    // Sync challenges (manuel côté front)
    try {
      const { data: s } = await api.post<ChallengeSyncStats>('/my/challenges/sync')
      sync.value = s
      toast.success('Challenges synchronisés')
    } catch (e: unknown) {
      const description = isAxiosError(e)
        ? ((e.response?.data as { detail?: string } | undefined)?.detail ?? 'Impossible de synchroniser.')
        : 'Impossible de synchroniser.'
      toast.error('Synchronisation partielle', { description })
    }
  } catch (e: unknown) {
    // Check if it's an Axios error with response
    if (isAxiosError(e) && e.response) {
      // HTTP error with response
      const status = e.response.status;
      const detail = (e.response.data as { detail?: string } | undefined)?.detail;

      if (status === 400) {
        error.value = detail || 'Fichier GPX/ZIP invalide ou mal formé.'
      } else if (status === 413) {
        error.value = detail || 'Fichier trop volumineux (limite dépassée).'
      } else {
        error.value = detail ?? (status ? `Erreur ${status}` : 'Import impossible.')
      }
    } else if (isAxiosError(e) && (e.code === 'ERR_NETWORK' || e.code === 'ECONNRESET')) {
      // Network error - likely a 413 that was converted to network error by Vite proxy
      error.value = 'Fichier trop volumineux (connexion réinitialisée).'
    } else {
      // Other error types
      const detail = isAxiosError(e)
        ? ((e.response?.data as { detail?: string } | undefined)?.detail || e.message)
        : 'Import impossible.'
      error.value = detail
    }

    toast.error('Import échoué', { description: error.value })
  } finally {
    loading.value = false
  }
}
</script>