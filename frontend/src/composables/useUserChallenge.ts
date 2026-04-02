// src/composables/useUserChallenge.ts
import { ref, computed } from "vue";
import api from "@/api/http";
import DOMPurify from "dompurify";
import { useApiErrorHandler } from "@/composables/useApiErrorHandler";
import type { UserChallengeDetail } from "@/types/challenges";

export function useUserChallenge(ucId: string) {
  const uc = ref<UserChallengeDetail | null>(null);
  const loadingDetail = ref(false);
  const errorDetail = ref<string | null>(null);
  const { handleApiError } = useApiErrorHandler();

  const safeDescription = computed(() => {
    const html = uc.value?.challenge?.description ?? "";
    try {
      return DOMPurify.sanitize(html);
    } catch {
      return html;
    }
  });

  async function fetchDetail() {
    loadingDetail.value = true;
    errorDetail.value = null;
    try {
      const { data } = await api.get(`/my/challenges/${ucId}`);
      uc.value = data;
    } catch (e: unknown) {
      errorDetail.value = handleApiError(e).message;
    } finally {
      loadingDetail.value = false;
    }
  }

  return { uc, loadingDetail, errorDetail, safeDescription, fetchDetail };
}
