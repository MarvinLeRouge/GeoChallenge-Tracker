import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'

// Auth
const authRoutes = [
  { path: '/login', name: 'auth/login', component: () => import('@/pages/auth/Login.vue') },
  { path: '/register', name: 'auth/register', component: () => import('@/pages/auth/Register.vue') },
]

// Caches
const cachesRoutes = [
  { path: '/caches/import-gpx', name: 'caches/import-gpx', 
    component: () => import('@/pages/caches/ImportGpx.vue') 
  },
  { path: '/caches/by-filter', name: 'caches/by-filter',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: { title: 'Recherche par filtres', message: 'Cette page arrive bientôt.', helpTo: '/help/caches' },
    meta: { dense: true, noFabPadding: true }    
  },
  { path: '/caches/within-bbox', name: 'caches/within-bbox',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: { title: 'Recherche par bbox', message: 'Cette page arrive bientôt.', helpTo: '/help/caches' },
    meta: { dense: true, noFabPadding: true }    
  },
  { path: '/caches/within-radius', name: 'caches-radius',
    component: () => import('@/pages/caches/WithinRadius.vue'),
    meta: { dense: true, noFabPadding: true }
  },
  { path: '/caches/map-demo', name: 'caches-map-demo',
    component: () => import('@/pages/caches/MapDemo.vue'),
    meta: { dense: true, noFabPadding: true }
  }
  
]

// Challenges (placeholder)
const challengesRoutes = [
  {
    path: '/my/challenges',
    name: 'my-challenges',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: { title: 'Mes challenges', message: 'Cette page arrive bientôt.', helpTo: '/help/challenges' },
    // planned: component: () => import('@/pages/challenges/MyChallenges.vue')
  },
  {
    path: '/my/challenges/:ucId',
    name: 'uc-detail',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: r => ({ title: 'Détail du challenge', message: `UC: ${r.params.ucId}`, helpTo: '/help/challenges' }),
    // planned: component: () => import('@/pages/challenges/ChallengeDetail.vue')
  },
  {
    path: '/my/challenges/:ucId/tasks',
    name: 'uc-tasks',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: { title: 'Tâches du challenge', message: 'Configuration à venir.', helpTo: '/help/challenges' },
    // planned: component: () => import('@/pages/challenges/UCTasks.vue')
  },
  {
    path: '/my/challenges/:ucId/progress',
    name: 'uc-progress',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: { title: 'Progression', message: 'Visualisation à venir.', helpTo: '/help/progression' },
    // planned: component: () => import('@/pages/challenges/UCProgress.vue')
  },
  {
    path: '/my/challenges/:ucId/targets',
    name: 'uc-targets',
    component: () => import('@/pages/_NotImplemented.vue'),
    props: { title: 'Targets du challenge', message: 'Carte à venir.', helpTo: '/help/targets' },
    meta: { dense: true, noFabPadding: true },
    // planned: component: () => import('@/pages/challenges/UCTargets.vue')
  },
]

// Targets
//const targetsRoutes = []
// Help
// const helpRoutes = []

const routes = [
  { path: '/', name: 'home', component: () => import('@/pages/Home.vue') },
  ...authRoutes, ...cachesRoutes, ...challengesRoutes,

  { path: '/protected', name: 'protected', component: () => import('@/pages/auth/Protected.vue') }, // pour tests

  { path: '/:pathMatch(.*)*', name: '404', component: () => import('@/pages/404.vue') },
]

const router = createRouter({
  history: createWebHistory(), 
  routes,
  scrollBehavior: (to, from, saved) => saved ?? (to.hash ? { el: to.hash } : { top: 0 }),
})

const PUBLIC_NAMES = new Set(['home', 'legal', '404', 'auth/login','auth/register','auth/verify-email','auth/resend-verification'])
const PUBLIC_PREFIXES = ['/help']

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.init()

  // protégé ?
  const isPublic = PUBLIC_NAMES.has(String(to.name||'')) || PUBLIC_PREFIXES.some(p => to.path.startsWith(p))  
  if (!isPublic && !auth.isAuthenticated) return { name: 'auth/login', query: { redirect: to.fullPath } }
  if (isPublic && auth.isAuthenticated && (to.name==='auth/login'||to.name==='auth/register')) return { path: '/' }
})

export default router
