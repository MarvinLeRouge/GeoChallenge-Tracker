<template>
  <form
    class="space-y-4 max-w-sm mx-auto"
    @submit.prevent="submit"
  >
    <h1 class="text-xl font-semibold">
      Créer un compte
    </h1>

    <div class="space-y-1">
      <label class="text-sm font-medium">Nom d'utilisateur</label>
      <input
        v-model.trim="username"
        type="text"
        class="border rounded w-full p-2"
        autocomplete="username"
        required
      >
    </div>

    <div class="space-y-1">
      <label class="text-sm font-medium">Email</label>
      <input
        v-model.trim="email"
        type="email"
        class="border rounded w-full p-2"
        autocomplete="email"
        required
      >
    </div>

    <div class="space-y-1">
      <label class="text-sm font-medium">Mot de passe</label>
      <input
        v-model="password"
        type="password"
        class="border rounded w-full p-2"
        autocomplete="new-password"
        required
      >
      <p class="text-xs text-gray-500">
        8+ caractères, mélange conseillé (majuscules, chiffres, symboles).
      </p>
    </div>

    <div class="space-y-1">
      <label class="text-sm font-medium">Confirmation mot de passe</label>
      <input
        v-model="confirm"
        type="password"
        class="border rounded w-full p-2"
        autocomplete="new-password"
        required
      >
      <p
        v-if="confirm && password !== confirm"
        class="text-xs text-red-600"
      >
        Ne correspond pas.
      </p>
    </div>

    <button
      class="border rounded px-3 py-2"
      :disabled="loading || !canSubmit"
    >
      {{ loading ? 'Création…' : 'Créer mon compte' }}
    </button>

    <p
      v-if="error"
      class="text-sm text-red-600"
    >
      {{ error }}
    </p>
    <p class="text-sm">
      Déjà un compte ?
      <RouterLink
        to="/login"
        class="underline"
      >
        Se connecter
      </RouterLink>
    </p>
  </form>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/http'
import { toast } from 'vue-sonner'
import { isAxiosError } from 'axios'
import type { FastAPIValidationItem } from '@/types/http'
import { getDetail } from '@/utils/http'

const router = useRouter()
const username = ref(''), email = ref(''), password = ref(''), confirm = ref('')
const canSubmit = computed(() => password.value.length > 0 && password.value === confirm.value)
const loading = ref(false)
const error = ref('')

async function submit() {
  if (!canSubmit.value) { toast.error('Sécurité du mot de passe', { description: 'Les mots de passe ne correspondent pas.' }); return }
  error.value = ''
  loading.value = true
  try {
    await api.post('/auth/register', { username: username.value, email: email.value, password: password.value })
    toast.success('Compte créé. Vérifie ton email (lien valable 24h).')
    router.replace('/login')
  } catch (e: unknown) {
    const status = isAxiosError(e) ? e.response?.status : undefined
    const data = (isAxiosError(e) ? e.response?.data : undefined)
    const detail = isAxiosError(e) ? getDetail(data) : undefined

    // util: transforme detail FastAPI (liste) en texte — sans any
    const toText = (d: unknown): string => {
      if (typeof d === 'string') return d
      if (Array.isArray(d)) return d.map(x => x.msg ?? '').filter(Boolean).join('\n')
      return ''
    }

    if (status === 422) {
      const txt = toText(detail)
      const items: FastAPIValidationItem[] = Array.isArray(detail) ? detail : []
      const isPwd = items.some(x =>
        (Array.isArray(x.loc) && x.loc.includes('password')) || /password|mot de passe/i.test(x.msg ?? '')
      )
      const title = isPwd ? 'Sécurité du mot de passe' : 'Champs invalides'
      error.value = txt || 'Veuillez corriger les champs.'
      toast.error(title, { description: error.value })
    } else if (status === 400) {
      error.value = toText(detail) || 'Mot de passe trop faible.'
      toast.error('Sécurité du mot de passe', { description: error.value })
    } else if (status === 409) {
      error.value = 'Nom d’utilisateur ou email déjà utilisés.'
      toast.error('Inscription impossible', { description: error.value })
    } else {
      error.value = typeof detail === 'string' ? detail : 'Inscription impossible.'
      toast.error('Erreur', { description: error.value })
    }
  } finally {
    loading.value = false
  }
}
</script>