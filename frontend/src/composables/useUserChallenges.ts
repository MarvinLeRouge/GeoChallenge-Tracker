// src/composables/useUserChallenges.ts
import { ref } from 'vue'
import api from '@/api/http'
import { useApiErrorHandler } from '@/composables/useApiErrorHandler'
import type { UserChallengeListItem } from '@/types/challenges'

export function useUserChallenges() {
  const challenges = ref<UserChallengeListItem[]>([])
  const page = ref(1)
  const pageSize = ref(20)
  const nbPages = ref(1)
  const nbItems = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const { handleApiError } = useApiErrorHandler()

  async function fetchChallenges(filterStatus?: string) {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, unknown> = {
        page: page.value,
        page_size: pageSize.value,
      }
      if (filterStatus && filterStatus !== 'all') params.status = filterStatus

      const { data } = await api.get('/my/challenges', { params })
      challenges.value = data.items ?? []
      nbItems.value = data.nb_items ?? challenges.value.length
      nbPages.value = data.nb_pages ?? Math.max(1, Math.ceil(nbItems.value / pageSize.value))
    } catch (e: unknown) {
      error.value = handleApiError(e).message
    } finally {
      loading.value = false
    }
  }

  return { challenges, page, pageSize, nbPages, nbItems, loading, error, fetchChallenges }
}
