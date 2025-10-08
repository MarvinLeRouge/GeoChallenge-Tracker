// src/composables/useUserChallenge.ts
import { ref, computed } from 'vue'
import api from '@/api/http'
import DOMPurify from 'dompurify'

export function useUserChallenge(ucId: string) {
    const uc = ref<any | null>(null)
    const loadingDetail = ref(false)
    const errorDetail = ref<string | null>(null)

    const safeDescription = computed(() => {
        const html = uc.value?.challenge?.description ?? ''
        try { return DOMPurify.sanitize(html) } catch { return html }
    })

    async function fetchDetail() {
        loadingDetail.value = true
        errorDetail.value = null
        try {
            const { data } = await api.get(`/my/challenges/${ucId}`)
            uc.value = data
        } catch (e: any) {
            errorDetail.value = e?.message ?? 'Erreur de chargement'
        } finally {
            loadingDetail.value = false
        }
    }

    return { uc, loadingDetail, errorDetail, safeDescription, fetchDetail }
}
