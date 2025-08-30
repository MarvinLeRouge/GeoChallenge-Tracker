<template>
    <form class="space-y-4 max-w-sm mx-auto" @submit.prevent="submit">
        <h1 class="text-xl font-semibold">Créer un compte</h1>

        <div class="space-y-1">
            <label class="text-sm font-medium">Nom d'utilisateur</label>
            <input v-model.trim="username" type="text" class="border rounded w-full p-2" autocomplete="username"
                required />
        </div>

        <div class="space-y-1">
            <label class="text-sm font-medium">Email</label>
            <input v-model.trim="email" type="email" class="border rounded w-full p-2" autocomplete="email" required />
        </div>

        <div class="space-y-1">
            <label class="text-sm font-medium">Mot de passe</label>
            <input v-model="password" type="password" class="border rounded w-full p-2" autocomplete="new-password"
                required />
            <p class="text-xs text-gray-500">8+ caractères, mélange conseillé (majuscules, chiffres, symboles).</p>
        </div>

        <button class="border rounded px-3 py-2" :disabled="loading">
            {{ loading ? 'Création…' : 'Créer mon compte' }}
        </button>

        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
        <p class="text-sm">
            Déjà un compte ?
            <RouterLink to="/login" class="underline">Se connecter</RouterLink>
        </p>
    </form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/http'
import { toast } from 'vue-sonner'

const router = useRouter()
const username = ref(''), email = ref(''), password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
    error.value = ''
    loading.value = true
    try {
        await api.post('/auth/register', { username: username.value, email: email.value, password: password.value })
        toast.success('Compte créé. Vérifie ton email (lien valable 24h).')
        router.replace('/login')
    } catch (e: any) {
        const s = e?.response?.status
        const data = e?.response?.data
        const detail = data?.msg ?? data?.detail
        // util: transforme le detail FastAPI (liste) en texte
        const toText = (d:any) =>
            Array.isArray(d) ? d.map((x:any) => x?.msg || '').filter(Boolean).join('\n')
            : (typeof d === 'string' ? d : '')

        if (s === 422) {
            const txt = toText(detail)
            const isPwd = (Array.isArray(detail) ? detail : []).some((x: any) =>
                (x?.loc || []).includes('password') || /password|mot de passe/i.test(x?.msg || '')
            )
            const title = isPwd ? 'Sécurité du mot de passe' : 'Champs invalides'
            error.value = txt || 'Veuillez corriger les champs.'
            toast.error(title, { description: error.value })
        } else if (s === 400) {
            error.value = toText(detail) || 'Mot de passe trop faible.'
            toast.error('Sécurité du mot de passe', { description: error.value })
        } else if (s === 409) {
            error.value = 'Nom d’utilisateur ou email déjà utilisés.'
            toast.error('Inscription impossible', { description: error.value })
        } else {
            error.value = data?.detail || 'Inscription impossible.'
            toast.error('Erreur', { description: error.value })
        }
    } finally {
        loading.value = false
    }
}
</script>