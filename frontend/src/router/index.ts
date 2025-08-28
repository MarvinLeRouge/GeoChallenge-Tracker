import { createRouter, createWebHistory } from 'vue-router'

export const routes = [
  { path: '/', name: 'home', component: () => import('@/pages/HomeDummy.vue') },
  { path: '/:pathMatch(.*)*', name: '404', component: () => import('@/pages/NotFound.vue') }
]

const router = createRouter({ history: createWebHistory(), routes })
export default router
