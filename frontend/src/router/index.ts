import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const routes = [
  { path: '/', name: 'home', component: () => import('@/pages/HomeDummy.vue') },
  { path: '/login', name: 'login', component: () => import('@/pages/auth/Login.vue') },
  { path: '/register', name: 'register', component: () => import('@/pages/auth/Register.vue') },
  { path: '/protected', name: 'protected', meta: { requiresAuth: true }, component: () => import('@/pages/auth/Protected.vue') },
  { path: '/:pathMatch(.*)*', name: '404', component: () => import('@/pages/NotFound.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.init()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if ((to.name === 'login' || to.name === 'register') && auth.isAuthenticated) {
    return { name: 'home' }
  }
})

export default router
