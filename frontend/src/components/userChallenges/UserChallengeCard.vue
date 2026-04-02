<!-- src/components/userChallenges/UserChallengeCard.vue -->
<template>
  <div
    class="rounded-lg border shadow-sm p-3 transition"
    :class="zebra ? 'bg-gray-50' : 'bg-white'"
  >
    <h3 class="font-semibold flex flex-wrap items-baseline gap-2">
      <CheckCircleIcon
        v-if="challenge.status === 'accepted'"
        class="w-5 h-5 text-green-600 shrink-0"
        aria-hidden="true"
      />
      <XCircleIcon
        v-else-if="challenge.status === 'dismissed'"
        class="w-5 h-5 text-red-600 shrink-0"
        aria-hidden="true"
      />
      <ClockIcon
        v-else-if="
          challenge.status === 'pending' &&
          challenge.computed_status != 'completed'
        "
        class="w-5 h-5 text-gray-600 shrink-0"
        aria-hidden="true"
      />
      <TrophyIcon
        v-else-if="
          challenge.status === 'completed' ||
          challenge.computed_status === 'completed'
        "
        class="w-5 h-5 text-gold-600 shrink-0"
        aria-hidden="true"
      />

      <span>
        {{ challenge.challenge.name }}
      </span>
      <span
        v-if="
          challenge.status === 'accepted' && challenge.progress?.percent != null
        "
        class="text-sm font-semibold text-gray-600"
        >{{ Math.round(challenge.progress.percent) }}%</span
      >
    </h3>

    <div
      class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-600"
    >
      <!-- Lien vers Geocaching -->
      <a
        v-if="challenge.cache?.GC"
        :href="`https://www.geocaching.com/geocache/${challenge.cache.GC}`"
        target="_blank"
        rel="noopener"
        class="flex items-center gap-1 hover:text-blue-600 truncate"
        title="Ouvrir sur Geocaching.com"
      >
        <ArrowTopRightOnSquareIcon class="w-4 h-4 shrink-0" />
        <span class="font-mono">{{ challenge.cache.GC }}</span>
      </a>

      <!-- Difficulty / Terrain -->
      <span
        v-if="challenge.cache?.difficulty && challenge.cache?.terrain"
        class="flex items-center gap-1 text-gray-700"
      >
        <FireIcon
          class="w-4 h-4"
          :class="difficultyColor(challenge.cache.difficulty)"
        />
        <span
          >D{{ challenge.cache.difficulty }} / T{{
            challenge.cache.terrain
          }}</span
        >
      </span>
    </div>

    <div class="mt-2">
      <div
        v-if="challenge.progress && challenge.progress.percent !== null"
        class="flex items-center gap-2"
      >
        <div class="flex-1 bg-gray-200 rounded h-2 overflow-hidden">
          <div
            class="h-full"
            :style="progressBarStyle(challenge.progress.percent)"
          />
        </div>
        <span class="text-xs text-gray-500 shrink-0 w-8 text-right">
          {{ Math.round(challenge.progress.percent) }}%
        </span>
      </div>
      <p v-else class="text-xs text-gray-400">Pas encore commencé</p>
    </div>

    <!-- Actions (icônes ronds) -->
    <div class="flex flex-wrap gap-2 mt-3">
      <!-- Détails -->
      <button
        class="p-2 rounded-full border bg-white hover:bg-gray-100"
        title="Détails"
        @click="$emit('details', challenge)"
      >
        <InformationCircleIcon class="w-5 h-5" />
      </button>

      <!-- Accept (caché si accepted/completed OU computed_status completed) -->
      <button
        v-if="
          !['accepted', 'completed'].includes(challenge.status) &&
          challenge.computed_status !== 'completed'
        "
        class="p-2 rounded-full border bg-white hover:bg-green-50"
        title="Accepter"
        @click="$emit('accept', challenge)"
      >
        <CheckIcon class="w-5 h-5" />
      </button>

      <!-- Dismiss (caché si dismissed/completed OU computed_status completed) -->
      <button
        v-if="
          !['dismissed', 'completed'].includes(challenge.status) &&
          challenge.computed_status !== 'completed'
        "
        class="p-2 rounded-full border bg-white hover:bg-red-50"
        title="Ignorer"
        @click="$emit('dismiss', challenge)"
      >
        <XMarkIcon class="w-5 h-5" />
      </button>

      <!-- Reset vers pending (si accepted ou dismissed) -->
      <button
        v-if="['accepted', 'dismissed'].includes(challenge.status)"
        class="p-2 rounded-full border bg-white hover:bg-amber-50"
        title="Réinitialiser (pending)"
        @click="$emit('reset', challenge)"
      >
        <ArrowUturnLeftIcon class="w-5 h-5" />
      </button>

      <!-- Tasks -->
      <button
        v-if="
          ['accepted', 'completed'].includes(challenge.status) ||
          challenge.computed_status === 'completed'
        "
        class="p-2 rounded-full border bg-white hover:bg-gray-100"
        title="Tâches"
        @click="$emit('tasks', challenge)"
      >
        <ClipboardDocumentListIcon class="w-5 h-5" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  TrophyIcon,
  InformationCircleIcon,
  CheckIcon,
  XMarkIcon,
  ArrowUturnLeftIcon,
  ClipboardDocumentListIcon,
  ArrowTopRightOnSquareIcon,
  FireIcon,
} from "@heroicons/vue/24/outline";

function progressBarStyle(percent: number) {
  const pct = Math.min(percent, 100);
  if (pct >= 100) {
    return { width: "100%", background: "#22c55e" };
  }
  return {
    width: "100%",
    background:
      "linear-gradient(to right, #ef4444 0%, #f97316 20%, #22c55e 55%)",
    clipPath: `inset(0 ${100 - pct}% 0 0)`,
  };
}

function difficultyColor(value: number | string | null | undefined) {
  const d = Number(value);
  if (isNaN(d)) return "text-gray-400";
  if (d <= 1.5) return "text-green-500";
  if (d <= 2.5) return "text-yellow-500";
  if (d <= 3.5) return "text-orange-500";
  if (d <= 4.5) return "text-red-500";
  return "text-purple-600";
}

type Progress = {
  percent: number | null;
  tasks_done: number | null;
  tasks_total: number | null;
  checked_at: string | null;
};

type UserChallenge = {
  id: string;
  status: "pending" | "accepted" | "dismissed" | "completed";
  computed_status: string | null;
  effective_status: "pending" | "accepted" | "dismissed" | "completed";
  progress: Progress | null;
  updated_at: string | null;
  challenge: { id: string; name: string };
  cache: {
    id: string;
    GC: string;
    difficulty?: number | null;
    terrain?: number | null;
  };
};

defineProps<{
  challenge: UserChallenge;
  zebra?: boolean;
}>();

defineEmits<{
  (e: "details", challenge: UserChallenge): void;
  (e: "accept", challenge: UserChallenge): void;
  (e: "dismiss", challenge: UserChallenge): void;
  (e: "reset", challenge: UserChallenge): void;
  (e: "tasks", challenge: UserChallenge): void;
}>();
</script>

<style scoped>
/* ta couleur or déjà utilisée */
.text-gold-600 {
  color: #daa520;
}
</style>
