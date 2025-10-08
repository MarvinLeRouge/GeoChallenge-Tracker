import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import type { RouteLocationNormalized } from 'vue-router'

// Auth
const authRoutes = [
  {
    path: '/login',
    name: 'auth/login',
    component: () => import('@/pages/auth/Login.vue'),
    meta: { title: 'Identification' }
  },
  {
    path: '/register',
    name: 'auth/register',
    component: () => import('@/pages/auth/Register.vue'),
    meta: { title: 'Inscription' }
  },
]

// Caches
const cachesRoutes = [
  {
    path: '/caches/import-gpx',
    name: 'caches/import-gpx',
    component: () => import('@/pages/caches/ImportGpx.vue'),
    meta: { title: 'Caches - Import GPX' },
  },
  {
    path: '/caches/by-filter',
    name: 'caches/by-filter',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: { title: 'Recherche par filtres', message: 'Cette page arrive bientôt.', helpTo: '/help/caches' },
    meta: { dense: true, noFabPadding: true, title: 'Caches - Par filtre' }
  },
  {
    path: '/caches/within-bbox',
    name: 'caches/within-bbox',
    component: () => import('@/pages/caches/WithinBbox.vue'),
    meta: { dense: true, noFabPadding: true, title: 'Caches - Zone géographique rectangulaire' }
  },
  {
    path: '/caches/within-radius',
    name: 'caches-radius',
    component: () => import('@/pages/caches/WithinRadius.vue'),
    meta: { dense: true, noFabPadding: true, title: 'Caches - Zone géographique circulaire' }
  },
  {
    path: '/caches/map-demo',
    name: 'caches-map-demo',
    component: () => import('@/pages/caches/MapDemo.vue'),
    meta: { dense: true, noFabPadding: true, title: 'Map - Démo' }
  }

]

// Challenges (placeholder)
const challengesRoutes = [
  {
    path: '/my/challenges',
    name: 'userChallengeList',
    component: () => import('@/pages/userChallenges/List.vue'),
    meta: { title: 'Mes challenges - Liste' },
  },
  {
    path: '/my/challenges/:id',
    name: 'userChallengeDetails',
    component: () => import('@/pages/userChallenges/Details.vue'),
    meta: { title: 'Mes challenges - Détails' },
  },
  {
    path: '/my/challenges/:id/tasks',
    name: 'userChallengeTasks',
    component: () => import('@/pages/userChallenges/Tasks.vue'),
    meta: { title: 'Mes challenges - Tâches' },
  },
  {
    path: '/my/challenges/:ucId/progress',
    name: 'uc-progress',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: { title: 'Progression', message: 'Visualisation à venir.', helpTo: '/help/progression' },
    // planned: component: () => import('@/pages/challenges/UCProgress.vue')
    meta: { title: 'Mes challenges - Progrès' },
  },
  {
    path: '/my/challenges/:ucId/targets',
    name: 'uc-targets',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: { title: 'Targets du challenge', message: 'Carte à venir.', helpTo: '/help/targets' },
    meta: { dense: true, noFabPadding: true, title: 'Mes challenges - Targets' },
    // planned: component: () => import('@/pages/challenges/UCTargets.vue')
  },
]

// Targets
//const targetsRoutes = []
// Help
// const helpRoutes = []

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/pages/Home.vue'),
    meta: { title: 'Accueil' },
  },
  {
    path: '/legal',
    name: 'legal',
    component: () => import('@/pages/misc/Legal.vue'),
    meta: { title: 'Mentions légales' },
  },
  ...authRoutes, ...cachesRoutes, ...challengesRoutes,

  {
    path: '/protected',
    name: 'protected',
    component: () => import('@/pages/auth/Protected.vue'),
    meta: { title: 'Zone réservée' },
  }, // pour tests

  {
    path: '/:pathMatch(.*)*',
    name: '404',
    component: () => import('@/pages/404.vue'),
    meta: { title: 'Page non trouvée' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (to, from, saved) => saved ?? (to.hash ? { el: to.hash } : { top: 0 }),
})

const PUBLIC_NAMES = new Set(['home', 'legal', '404', 'auth/login', 'auth/register', 'auth/verify-email', 'auth/resend-verification'])
const PUBLIC_PREFIXES = ['/help']

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.init()

  // protégé ?
  const isPublic = PUBLIC_NAMES.has(String(to.name || '')) || PUBLIC_PREFIXES.some(p => to.path.startsWith(p))
  if (!isPublic && !auth.isAuthenticated) return { name: 'auth/login', query: { redirect: to.fullPath } }
  if (isPublic && auth.isAuthenticated && (to.name === 'auth/login' || to.name === 'auth/register')) return { path: '/' }
})

router.afterEach((to) => {
  const defaultTitle = 'GeoChallenge Tracker'
  document.title = to.meta.title
    ? `${to.meta.title} | ${defaultTitle}`
    : defaultTitle
})


export default router
