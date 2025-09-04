import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const routes = [
  { path: '/', name: 'home', component: () => import('@/pages/Home.vue') },
  { path: '/login', name: 'login', component: () => import('@/pages/auth/Login.vue') },
  { path: '/register', name: 'register', component: () => import('@/pages/auth/Register.vue') },
  { path: '/protected', name: 'protected', component: () => import('@/pages/auth/Protected.vue') }, // pour tests
  { path: '/:pathMatch(.*)*', name: '404', component: () => import('@/pages/404.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

const PUBLIC_NAMES = new Set(['home', '404', 'login','register','verify-email','resend-verification'])
const PUBLIC_PREFIXES = ['/help']

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.init()

  // protégé ?
  const isPublic = PUBLIC_NAMES.has(String(to.name||'')) || PUBLIC_PREFIXES.some(p => to.path.startsWith(p))  
  if (!isPublic && !auth.isAuthenticated) return { name: 'login', query: { redirect: to.fullPath } }
  if (isPublic && auth.isAuthenticated && (to.name==='login'||to.name==='register')) return { path: '/' }
})

export default router
