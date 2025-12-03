<template>
  <form
    class="space-y-3 max-w-sm"
    @submit.prevent="submit"
  >
    <h2 class="text-xl font-semibold">
      Connexion
    </h2>

    <input
      v-model.trim="identifier"
      type="text"
      placeholder="Email ou nom d'utilisateur"
      name="identifier"
      class="border p-2 w-full"
      autocomplete="username"
      required
    >

    <input
      v-model="password"
      type="password"
      placeholder="Mot de passe"
      name="password"
      class="border p-2 w-full"
      autocomplete="current-password"
      required
    >

    <button
      type="submit"
      class="border px-3 py-2"
      :disabled="loading"
    >
      {{ loading ? 'Connexion…' : 'Se connecter' }}
    </button>

    <p
      v-if="error"
      class="text-red-600 text-sm"
    >
      {{ error }}
    </p>
  </form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { useApiErrorHandler } from '@/composables/useApiErrorHandler'

const identifier = ref('')
const password = ref('')
const loading = ref(false)
const { error, handleApiError, clearError } = useApiErrorHandler()

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const submit = async () => {
  loading.value = true
  clearError()
  try {
    await auth.login({ identifier: identifier.value, password: password.value })
    router.replace((route.query.redirect as string) || '/')
  } catch (e: unknown) {
    handleApiError(e)
  } finally {
    loading.value = false
  }
}
</script>
