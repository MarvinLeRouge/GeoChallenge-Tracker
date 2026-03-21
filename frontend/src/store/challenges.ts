// src/store/challenges.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/http'
import { useApiErrorHandler } from '@/composables/useApiErrorHandler'
import type { UserChallengeListItem } from '@/types/challenges'

export const useChallengesStore = defineStore('challenges', () => {
  const items = ref<UserChallengeListItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const page = ref(1)
  const pageSize = ref(20)
  const nbPages = ref(1)
  const nbItems = ref(0)
  const { handleApiError } = useApiErrorHandler()

  async function fetchList(filterStatus?: string) {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, unknown> = {
        page: page.value,
        page_size: pageSize.value,
      }
      if (filterStatus && filterStatus !== 'all') params.status = filterStatus

      const { data } = await api.get('/my/challenges', { params })
      items.value = data.items ?? []
      nbItems.value = data.nb_items ?? items.value.length
      nbPages.value = data.nb_pages ?? Math.max(1, Math.ceil(nbItems.value / pageSize.value))
    } catch (e: unknown) {
      error.value = handleApiError(e).message
    } finally {
      loading.value = false
    }
  }

  function updateItem(id: string, patch: Partial<UserChallengeListItem>) {
    const idx = items.value.findIndex(c => c.id === id)
    if (idx !== -1) items.value[idx] = { ...items.value[idx], ...patch }
  }

  return { items, loading, error, page, pageSize, nbPages, nbItems, fetchList, updateItem }
})
