<!-- src/pages/userChallenges/List.vue -->
<template>
  <div class="p-4 space-y-4">
    <!-- Filtres (boutons ronds) -->
    <div class="flex flex-wrap gap-3 justify-center">
      <button
        v-for="s in ['all', 'pending', 'accepted', 'dismissed', 'completed']"
        :key="s"
        class="p-2 rounded-full border flex items-center justify-center w-10 h-10 transition"
        :class="
          filterStatus === s
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white text-gray-600 hover:bg-gray-50'
        "
        :title="statusLabels[s]"
        :aria-label="statusLabels[s]"
        @click="setFilter(s as any)"
      >
        <component
          :is="
            s === 'all'
              ? AdjustmentsHorizontalIcon
              : statusIcons[s as keyof typeof statusIcons]
          "
          class="w-5 h-5"
        />
      </button>
    </div>

    <!-- Etat / erreurs -->
    <div v-if="store.error" class="text-center text-red-600 text-sm">
      {{ store.error }}
    </div>
    <div v-if="store.loading" class="text-center text-gray-500">
      Chargement…
    </div>

    <!-- Liste -->
    <div v-if="!store.loading" class="space-y-3">
      <UserChallengeCard
        v-for="(ch, idx) in store.items"
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
        <span class="text-sm">Page {{ store.page }} / {{ store.nbPages }}</span>
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
import { computed, onMounted, watch, ref } from "vue";
import api from "@/api/http";
import { useRouter, useRoute } from "vue-router";
import UserChallengeCard from "@/components/userChallenges/UserChallengeCard.vue";
import { useChallengesStore } from "@/store/challenges";
import { useApiErrorHandler } from "@/composables/useApiErrorHandler";
import type { UserChallengeListItem } from "@/types/challenges";
import { toast } from "vue-sonner";

import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  TrophyIcon,
  AdjustmentsHorizontalIcon,
} from "@heroicons/vue/24/outline";

const router = useRouter();
const route = useRoute();
const { handleApiError } = useApiErrorHandler();
const store = useChallengesStore();

type UCStatus = UserChallengeListItem["status"];

const filterStatus = ref<"all" | UCStatus>(
  (route.query.status as "all" | UCStatus) || "all",
);
store.page = route.query.page ? parseInt(route.query.page as string, 10) : 1;

const statusIcons: Record<UCStatus, unknown> = {
  pending: ClockIcon,
  accepted: CheckCircleIcon,
  dismissed: XCircleIcon,
  completed: TrophyIcon,
};
const statusLabels: Record<string, string> = {
  all: "Tous",
  pending: "En attente",
  accepted: "Acceptés",
  dismissed: "Refusés",
  completed: "Complétés",
};
const canPrev = computed(() => store.page > 1);
const canNext = computed(() => store.page < store.nbPages && store.nbPages > 0);

function updateUrl() {
  const query: Record<string, string> = {};
  if (filterStatus.value !== "all") query.status = filterStatus.value;
  if (store.page > 1) query.page = store.page.toString();
  router.replace({ query });
}

watch([filterStatus, () => store.page], () => {
  updateUrl();
  store.fetchList(filterStatus.value);
});

onMounted(() => store.fetchList(filterStatus.value));

function setFilter(status: "all" | UCStatus) {
  if (filterStatus.value === status) return;
  filterStatus.value = status;
  store.page = 1;
}

function prevPage() {
  if (canPrev.value) store.page -= 1;
}
function nextPage() {
  if (canNext.value) store.page += 1;
}

function showDetails(ch: UserChallengeListItem) {
  router.push({ name: "userChallengeDetails", params: { id: ch.id } });
}

async function patchChallenge(ch: UserChallengeListItem, status: UCStatus) {
  store.loading = true;
  try {
    await api.patch(`/my/challenges/${ch.id}`, { status });
    store.updateItem(ch.id, { status });
    await store.fetchList(filterStatus.value);
    toast.success("Challenge mis à jour");
  } catch (e: unknown) {
    const msg = handleApiError(e).message;
    store.error = msg;
    toast.error("Erreur de mise à jour", { description: msg });
  } finally {
    store.loading = false;
  }
}

function acceptChallenge(ch: UserChallengeListItem) {
  patchChallenge(ch, "accepted");
}
function dismissChallenge(ch: UserChallengeListItem) {
  patchChallenge(ch, "dismissed");
}
function resetChallenge(ch: UserChallengeListItem) {
  patchChallenge(ch, "pending");
}

function manageTasks(ch: UserChallengeListItem) {
  router.push({ name: "userChallengeTasks", params: { id: ch.id } });
}
</script>
