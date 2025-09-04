<!-- src/pages/Home.vue -->
<template>
  <section class="max-w-screen-lg mx-auto space-y-12">
    <!-- HERO -->
    <header class="relative overflow-hidden rounded-2xl bg-gradient-to-b from-indigo-50 to-white ring-1 ring-indigo-100 p-6 md:p-10 text-center">
      <h1 class="text-3xl md:text-4xl font-extrabold tracking-tight">
        GeoChallenge Tracker
      </h1>
      <p class="mt-3 text-gray-600 max-w-2xl mx-auto">
        Oubliez les tableurs et les fichiers de notes interminables.
      </p>
      <p class="mt-3 text-gray-600 max-w-2xl mx-auto">
        Importez vos GPX, choisissez vos challenges et suivez votre progression.
      </p>
      <p class="mt-3 text-gray-600 max-w-2xl mx-auto">
        Utilisez la carte interactive pour trouver les meilleures caches pour avancer.
      </p>

      <div class="mt-6 flex flex-wrap items-center justify-center gap-3">
        <RouterLink
          v-if="!isAuthenticated"
          to="/register"
          class="inline-flex items-center rounded-lg border px-4 py-2 font-medium hover:bg-white/60 backdrop-blur"
        >
          Créer un compte
        </RouterLink>
        <RouterLink
          v-if="!isAuthenticated"
          to="/login"
          class="inline-flex items-center rounded-lg border px-4 py-2 font-medium hover:bg-white/60 backdrop-blur"
        >
          Se connecter
        </RouterLink>

        <RouterLink
          v-if="isAuthenticated"
          to="/caches/import-gpx"
          class="inline-flex items-center rounded-lg border px-4 py-2 font-medium hover:bg-white/60 backdrop-blur"
        >
          Importer un GPX
        </RouterLink>
        <RouterLink
          v-if="isAuthenticated"
          to="/my/challenges"
          class="inline-flex items-center rounded-lg border px-4 py-2 font-medium hover:bg-white/60 backdrop-blur"
        >
          Mes challenges
        </RouterLink>

        <a href="#how" class="inline-flex items-center rounded-lg border px-4 py-2 font-medium hover:bg-white/60">
          Commencer
        </a>
      </div>
    </header>

    <!-- PAS-À-PAS -->
    <section id="how" class="space-y-6">
      <h2 class="text-2xl font-semibold text-center">Comment ça marche ?</h2>

      <ol class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <!-- 1 -->
        <li class="group rounded-xl border p-4 hover:shadow-sm transition">
          <div class="flex items-start gap-3">
            <UserPlusIcon class="w-12 h-12 text-indigo-600 shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold">1 - Inscription gratuite</p>
              <p class="text-sm text-gray-600">Créez votre compte en quelques secondes.</p>
            </div>
          </div>
        </li>

        <!-- 2 -->
        <li class="group rounded-xl border p-4 hover:shadow-sm transition">
          <div class="flex items-start gap-3">
            <DocumentArrowUpIcon class="w-12 h-12 text-indigo-600 shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold">2 - Importez vos fichiers GPX</p>
              <p class="text-sm text-gray-600">Caches connues et trouvées pour alimenter vos listes.</p>
            </div>
          </div>
        </li>

        <!-- 3 -->
        <li class="group rounded-xl border p-4 hover:shadow-sm transition">
          <div class="flex items-start gap-3">
            <SparklesIcon class="w-12 h-12 text-indigo-600 shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold">3 - Détection automatique des challenges</p>
              <p class="text-sm text-gray-600">L’outil identifie automatiquement les caches challenges.</p>
            </div>
          </div>
        </li>

        <!-- 4 -->
        <li class="group rounded-xl border p-4 hover:shadow-sm transition">
          <div class="flex items-start gap-3">
            <CheckCircleIcon class="w-12 h-12 text-indigo-600 shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold">4 - Choisissez vos objectifs</p>
              <p class="text-sm text-gray-600">Acceptez ou ignorez en un clic, selon vos envies.</p>
            </div>
          </div>
        </li>

        <!-- 5 -->
        <li class="group rounded-xl border p-4 hover:shadow-sm transition">
          <div class="flex items-start gap-3">
            <AdjustmentsHorizontalIcon class="w-12 h-12 text-indigo-600 shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold">5 - Définissez les règles simplement</p>
              <p class="text-sm text-gray-600">
                Décrivez la ou les tâches des challenges acceptés à l'aide d'un langage créé spécifiquement pour ça.
              </p>
            </div>
          </div>
        </li>

        <!-- 6 -->
        <li class="group rounded-xl border p-4 hover:shadow-sm transition">
          <div class="flex items-start gap-3">
            <ArrowTrendingUpIcon class="w-12 h-12 text-indigo-600 shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold">6 - Suivi automatique de la progression</p>
              <p class="text-sm text-gray-600">Avancement, historique et date estimée d’achèvement.</p>
            </div>
          </div>
        </li>

        <!-- 7 -->
        <li class="group rounded-xl border p-4 hover:shadow-sm transition lg:col-span-3">
          <div class="flex items-start gap-3">
            <MapIcon class="w-12 h-12 text-indigo-600 shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold">7 - Carte interactive des caches utiles</p>
              <p class="text-sm text-gray-600">
                Visualisez les caches qui vous font progresser, avec priorisation suivant plusieurs critères.
              </p>
            </div>
          </div>
        </li>
      </ol>
    </section>

    <!-- TEASER / CTA -->
    <section class="text-center rounded-2xl border p-6 md:p-8 bg-gradient-to-b from-white to-indigo-50">
      <h3 class="text-2xl font-bold">Prêt ? Partez !</h3>
      <p class="text-gray-600 mt-2">Faites vos premiers pas et laissez GeoChallenge Tracker guider vos challenges.</p>

      <div class="mt-5 flex flex-wrap items-center justify-center gap-3">
        <RouterLink
          v-if="!isAuthenticated"
          to="/register"
          class="inline-flex items-center rounded-lg border px-4 py-2 font-medium hover:bg-white"
        >
          Créer un compte
        </RouterLink>
        <RouterLink
          v-if="!isAuthenticated"
          to="/login"
          class="inline-flex items-center rounded-lg border px-4 py-2 font-medium hover:bg-white"
        >
          Se connecter
        </RouterLink>

        <RouterLink
          v-if="isAuthenticated"
          to="/caches/import-gpx"
          class="inline-flex items-center rounded-lg border px-4 py-2 font-medium hover:bg-white"
        >
          Importer un GPX
        </RouterLink>
        <RouterLink
          v-if="isAuthenticated"
          to="/my/challenges"
          class="inline-flex items-center rounded-lg border px-4 py-2 font-medium hover:bg-white"
        >
          Mes challenges
        </RouterLink>
      </div>
    </section>

    <!-- AIDE -->
    <section class="space-y-3">
      <h2 class="text-xl font-semibold text-center">Besoin d’aide ?</h2>
      <p class="text-gray-600 text-sm text-center">
        Guides rapides :
        <RouterLink to="/help/caches" class="underline">Caches</RouterLink>,
        <RouterLink to="/help/challenges" class="underline">Challenges</RouterLink>,
        <RouterLink to="/help/progression" class="underline">Progression</RouterLink>,
        <RouterLink to="/help/targets" class="underline">Targets</RouterLink>,
        <RouterLink to="/help/profile" class="underline">Profil</RouterLink>.
      </p>
    </section>
  </section>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/store/auth'
import {
  UserPlusIcon,
  DocumentArrowUpIcon,
  SparklesIcon,
  CheckCircleIcon,
  AdjustmentsHorizontalIcon,
  ArrowTrendingUpIcon,
  MapIcon
} from '@heroicons/vue/24/outline'

const { isAuthenticated } = storeToRefs(useAuthStore())
</script>
