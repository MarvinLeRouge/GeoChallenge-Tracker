<template>
  <div class="p-4 space-y-4">
    <!-- Filtres (boutons ronds) -->
    <div class="flex gap-3 justify-center">
      <button
        v-for="s in ['all','pending','accepted','dismissed','completed']"
        :key="s"
        class="p-2 rounded-full border flex items-center justify-center w-10 h-10 transition"
        :class="filterStatus === s ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 hover:bg-gray-50'"
        @click="setFilter(s as any)"
        :title="s === 'all' ? 'Tous' : s"
        :aria-label="s === 'all' ? 'Tous' : s"
      >
        <component :is="s==='all'?AdjustmentsHorizontalIcon:statusIcons[s as keyof typeof statusIcons]" class="w-5 h-5" />
      </button>
    </div>

    <!-- Etat / erreurs -->
    <div v-if="error" class="text-center text-red-600 text-sm">{{ error }}</div>
    <div v-if="loading" class="text-center text-gray-500">Chargement…</div>

    <!-- Liste -->
    <div v-if="!loading" class="space-y-3">
      <div
        v-for="ch in challenges"
        :key="ch.id"
        class="rounded-lg border bg-white shadow-sm p-3"
      >
        <div class="flex justify-between items-start gap-3">
          <div class="min-w-0">
            <h3 class="font-semibold truncate">{{ ch.challenge.name }}</h3>
            <p class="text-sm text-gray-500">GC: {{ ch.cache.GC }}</p>
            <p class="text-xs text-gray-400">
              Màj: {{ new Date(ch.updated_at).toLocaleDateString() }}
            </p>
          </div>
          <component :is="statusIcons[ch.status]" class="w-6 h-6 text-gray-500 shrink-0" />
        </div>

        <div class="mt-2">
          <div v-if="ch.progress && ch.progress.percent !== null" class="w-full bg-gray-200 rounded h-2">
            <div class="bg-green-500 h-2 rounded" :style="{ width: ch.progress.percent + '%' }"></div>
          </div>
          <p v-else class="text-xs text-gray-400">Pas encore commencé</p>
        </div>

        <!-- Actions (icônes ronds) -->
        <div class="flex gap-2 mt-3">
          <button
            class="p-2 rounded-full border bg-white hover:bg-gray-100"
            @click="showDetails(ch)"
            title="Détails"
          >
            <InformationCircleIcon class="w-5 h-5" />
          </button>

          <button
            v-if="!['accepted','completed'].includes(ch.status)"
            class="p-2 rounded-full border bg-white hover:bg-green-50"
            @click="acceptChallenge(ch)"
            title="Accepter"
          >
            <CheckIcon class="w-5 h-5" />
          </button>

          <button
            v-if="!['dismissed','completed'].includes(ch.status)"
            class="p-2 rounded-full border bg-white hover:bg-red-50"
            @click="dismissChallenge(ch)"
            title="Refuser"
          >
            <XMarkIcon class="w-5 h-5" />
          </button>

          <button
            class="p-2 rounded-full border bg-white hover:bg-indigo-50"
            @click="manageTasks(ch)"
            title="Tâches"
          >
            <ClipboardDocumentListIcon class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Pagination -->
      <div class="flex justify-between items-center mt-4">
        <button
          class="px-3 py-2 rounded border bg-white disabled:opacity-50"
          :disabled="!canPrev"
          @click="prevPage"
        >
          Précédent
        </button>
        <span class="text-sm">Page {{ page }} / {{ nbPages }}</span>
        <button
          class="px-3 py-2 rounded border bg-white disabled:opacity-50"
          :disabled="!canNext"
          @click="nextPage"
        >
          Suivant
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '@/api/http'

// Heroicons 24/outline (cohérent avec ta home)
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  TrophyIcon,
  InformationCircleIcon,
  CheckIcon,
  XMarkIcon,
  ClipboardDocumentListIcon,
  AdjustmentsHorizontalIcon,
} from '@heroicons/vue/24/outline'

type Progress = {
  percent: number | null
  tasks_done: number | null
  tasks_total: number | null
  checked_at: string | null
}
type UserChallenge = {
  id: string
  status: 'pending' | 'accepted' | 'dismissed' | 'completed'
  computed_status: string | null
  effective_status: 'pending' | 'accepted' | 'dismissed' | 'completed'
  progress: Progress | null
  updated_at: string
  challenge: { id: string; name: string }
  cache: { id: string; GC: string }
}

const challenges = ref<UserChallenge[]>([])
const page = ref(1)
const pageSize = ref(20)
const nbPages = ref(1)
const nbItems = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)
const filterStatus = ref<'all' | UserChallenge['status']>('all')

const statusIcons: Record<UserChallenge['status'], any> = {
  pending: ClockIcon,
  accepted: CheckCircleIcon,
  dismissed: XCircleIcon,
  completed: TrophyIcon,
}

const canPrev = computed(() => page.value > 1)
const canNext = computed(() => page.value < nbPages.value && nbPages.value > 0)

async function fetchChallenges() {
  loading.value = true
  error.value = null
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filterStatus.value !== 'all') params.status = filterStatus.value

    const { data } = await api.get('/my/challenges', { params })
    challenges.value = data.items ?? []
    nbItems.value = data.nb_items ?? challenges.value.length
    // Si l’API peut renvoyer nb_pages, on le prend, sinon on calcule.
    nbPages.value = data.nb_pages ?? Math.max(1, Math.ceil((data.nb_items ?? 0) / (data.page_size ?? pageSize.value)))
  } catch (e: any) {
    error.value = e?.message ?? 'Erreur de chargement'
  } finally {
    loading.value = false
  }
}

onMounted(fetchChallenges)

function setFilter(status: 'all' | UserChallenge['status']) {
  if (filterStatus.value === status) return
  filterStatus.value = status
  page.value = 1
  fetchChallenges()
}

function prevPage() {
  if (!canPrev.value) return
  page.value -= 1
  fetchChallenges()
}
function nextPage() {
  if (!canNext.value) return
  page.value += 1
  fetchChallenges()
}

// Actions (branche tes endpoints si dispo)
async function showDetails(ch: UserChallenge) {
  // e.g. this.$router.push({ name: 'userChallengeDetail', params: { id: ch.id } })
}
async function acceptChallenge(ch: UserChallenge) {
  try {
    loading.value = true
    await api.post(`/my/challenges/${ch.id}/accept`)
    await fetchChallenges()
  } finally {
    loading.value = false
  }
}
async function dismissChallenge(ch: UserChallenge) {
  try {
    loading.value = true
    await api.post(`/my/challenges/${ch.id}/dismiss`)
    await fetchChallenges()
  } finally {
    loading.value = false
  }
}
async function manageTasks(ch: UserChallenge) {
  // e.g. this.$router.push({ name: 'userChallengeTasks', params: { id: ch.id } })
}
</script>

