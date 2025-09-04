<template>
  <form class="space-y-3 max-w-sm" @submit.prevent="submit">
    <h2 class="text-xl font-semibold">Connexion</h2>

    <input
      v-model.trim="identifier"
      type="text"
      placeholder="Email ou nom d'utilisateur"
      class="border p-2 w-full"
      autocomplete="username"
      required
    />

    <input
      v-model="password"
      type="password"
      placeholder="Mot de passe"
      class="border p-2 w-full"
      autocomplete="current-password"
      required
    />

    <button class="border px-3 py-2" :disabled="loading">
      {{ loading ? 'Connexion…' : 'Se connecter' }}
    </button>

    <p v-if="error" class="text-red-600 text-sm">{{ error }}</p>
  </form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const identifier = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const submit = async () => {
  loading.value = true
  error.value = ''
  try {
    await auth.login({ identifier: identifier.value, password: password.value })
    router.replace((route.query.redirect as string) || '/')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Échec de connexion'
  } finally {
    loading.value = false
  }
}
</script>
