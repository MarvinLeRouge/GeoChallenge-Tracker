<!-- src/pages/userChallenges/List.vue -->
<template>
  <div class="p-4 space-y-4">
    <!-- Filtres (boutons ronds) -->
    <div class="flex flex-wrap gap-3 justify-center">
      <button
        v-for="s in ['all', 'pending', 'accepted', 'dismissed', 'completed']"
        :key="s"
        class="p-2 rounded-full border flex items-center justify-center w-10 h-10 transition"
        :class="filterStatus === s ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 hover:bg-gray-50'"
        :title="statusLabels[s]"
        :aria-label="statusLabels[s]"
        @click="setFilter(s as any)"
      >
        <component
          :is="s === 'all' ? AdjustmentsHorizontalIcon : statusIcons[s as keyof typeof statusIcons]"
          class="w-5 h-5"
        />
      </button>
    </div>

    <!-- Etat / erreurs -->
    <div
      v-if="error"
      class="text-center text-red-600 text-sm"
    >
      {{ error }}
    </div>
    <div
      v-if="loading"
      class="text-center text-gray-500"
    >
      Chargement…
    </div>

    <!-- Liste -->
    <div
      v-if="!loading"
      class="space-y-3"
    >
      <UserChallengeCard
        v-for="(ch, idx) in challenges"
        :key="ch.id"
        :challenge="ch"
        :zebra="idx % 2 !== 0"
        @details="showDetails"
        @accept="acceptChallenge"
        @dismiss="dismissChallenge"
        @reset="resetChallenge"
        @tasks="manageTasks"
      />

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
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/api/http'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

import UserChallengeCard from '@/components/userChallenges/UserChallengeCard.vue'

// Heroicons 24/outline (cohérent avec ta home)
import {
    CheckCircleIcon,
    XCircleIcon,
    ClockIcon,
    TrophyIcon,
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
const pageSize = ref(20)
const nbPages = ref(1)
const nbItems = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)
const filterStatus = ref<'all' | UserChallenge['status']>(
    (route.query.status as any) || 'all'
)
const page = ref(
    route.query.page ? parseInt(route.query.page as string, 10) : 1
)
const statusIcons: Record<UserChallenge['status'], any> = {
    pending: ClockIcon,
    accepted: CheckCircleIcon,
    dismissed: XCircleIcon,
    completed: TrophyIcon,
}
const statusLabels: Record<string, string> = {
    all: 'Tous',
    pending: 'En attente',
    accepted: 'Acceptés',
    dismissed: 'Refusés',
    completed: 'Complétés',
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

// Mise à jour de l'URL quand les filtres changent
function updateUrl() {
    const query: Record<string, string> = {}
    if (filterStatus.value !== 'all') query.status = filterStatus.value
    if (page.value > 1) query.page = page.value.toString()

    router.replace({ query })
}

// Watch pour synchroniser URL ↔ état
watch([filterStatus, page], () => {
    updateUrl()
    fetchChallenges()
})

onMounted(fetchChallenges)

function setFilter(status: 'all' | UserChallenge['status']) {
    if (filterStatus.value === status) return
    filterStatus.value = status
    page.value = 1
}

function prevPage() {
    if (!canPrev.value) return
    page.value -= 1
}

function nextPage() {
    if (!canNext.value) return
    page.value += 1
}

// Actions (branche tes endpoints si dispo)
async function showDetails(ch: UserChallenge) {
    router.push({ name: 'userChallengeDetails', params: { id: ch.id } })
}
async function acceptChallenge(ch: UserChallenge) {
    try {
        loading.value = true
        await api.patch(`/my/challenges/${ch.id}`, {
            status: 'accepted',
        })
        await fetchChallenges()
    } catch (e: any) {
        console.error('Erreur accept:', e)
        error.value = e?.message ?? 'Erreur accept'
    } finally {
        loading.value = false
    }
}

async function dismissChallenge(ch: UserChallenge) {
    try {
        loading.value = true
        await api.patch(`/my/challenges/${ch.id}`, {
            status: 'dismissed',
        })
        await fetchChallenges()
    } catch (e: any) {
        console.error('Erreur dismiss:', e)
        error.value = e?.message ?? 'Erreur dismiss'
    } finally {
        loading.value = false
    }
}

async function resetChallenge(ch: UserChallenge) {
    try {
        loading.value = true
        await api.patch(`/my/challenges/${ch.id}`, {
            status: 'pending',
        })
        await fetchChallenges()
    } catch (e: any) {
        console.error('Erreur reset:', e)
        error.value = e?.message ?? 'Erreur reset'
    } finally {
        loading.value = false
    }
}

async function manageTasks(ch: UserChallenge) {
    console.log("tasks", ch.id)
    router.push({ name: 'userChallengeTasks', params: { id: ch.id } })
}
</script>
