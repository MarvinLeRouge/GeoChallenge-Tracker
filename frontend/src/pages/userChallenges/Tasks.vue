<!-- src/pages/userChallenges/Tasks.vue -->
<template>
    <!-- Contexte UC -->
    <div class="rounded-lg border bg-white p-4 shadow-sm">
        <h1 class="font-semibold text-lg break-words flex items-center gap-2">
            {{ uc?.challenge?.name || 'Challenge' }}
            <span v-if="uc?.cache?.GC" class="text-sm text-gray-500">· GC: {{ uc.cache.GC }}</span>
        </h1>

        <details class="mt-2">
            <summary class="cursor-pointer text-sm text-blue-600 hover:underline">
                Voir la description
            </summary>
            <div class="prose prose-sm max-w-none mt-2" v-html="safeDescription"></div>
        </details>
    </div>
    <div class="p-4 space-y-4">
        <div class="flex items-center gap-2">
            <button class="inline-flex items-center gap-2 text-sm" @click="router.back()">
                <ArrowLeftIcon class="w-5 h-5" /> Retour
            </button>

            <div class="ml-auto flex items-center gap-2">
                <button
                    class="px-3 py-2 rounded border bg-white hover:bg-gray-50 disabled:opacity-50 inline-flex items-center gap-2"
                    :disabled="loading" @click="validateAll" title="Valider la liste (sans enregistrer)">
                    <ClipboardDocumentCheckIcon class="w-5 h-5" />
                    Valider
                </button>
                <button
                    class="px-3 py-2 rounded border bg-white hover:bg-gray-50 disabled:opacity-50 inline-flex items-center gap-2"
                    :disabled="loading" @click="saveAll" title="Enregistrer toutes les tâches">
                    <ArrowUpOnSquareIcon class="w-5 h-5" />
                    Enregistrer
                </button>
                <button
                    class="px-3 py-2 rounded border bg-white hover:bg-gray-50 disabled:opacity-50 inline-flex items-center gap-2"
                    :disabled="loading" @click="addTask" title="Ajouter une tâche">
                    <PlusIcon class="w-5 h-5" />
                    Ajouter
                </button>
            </div>
        </div>

        <div v-if="error" class="text-center text-red-600 text-sm">{{ error }}</div>
        <div v-if="loading" class="text-center text-gray-500">Chargement…</div>

        <!-- Liste ordonnable -->
        <draggable v-model="tasks" item-key="id" handle=".drag-handle" class="space-y-3">
            <template #item="{ element: t, index: i }">
                <div class="rounded-lg border shadow-sm p-3" :class="i % 2 === 0 ? 'bg-white' : 'bg-gray-50'">
                    <div class="flex items-start gap-3">
                        <button class="drag-handle p-2 rounded border bg-white hover:bg-gray-50"
                            title="Glisser pour réordonner">
                            <Bars3Icon class="w-5 h-5" />
                        </button>

                        <div class="flex-1 min-w-0 space-y-3">
                            <!-- Titre -->
                            <div>
                                <label class="block text-xs text-gray-500 mb-1">Titre</label>
                                <input v-model="t.title" type="text" class="w-full border rounded px-3 py-2"
                                    placeholder="Titre de la tâche" />
                            </div>

                            <!-- Expression (textarea simple) -->
                            <div>
                                <label class="block text-xs text-gray-500 mb-1">Expression (JSON minimal)</label>
                                <textarea v-model="t.expression_json"
                                    class="w-full border rounded px-3 py-2 font-mono text-xs" rows="6"
                                    placeholder='{\n  "kind": "size_in",\n  "sizes": [{ "code": "L" }]\n}' />
                                <p class="text-[11px] text-gray-500 mt-1">
                                    Saisir seulement l’objet <code>expression</code> (pas la tâche complète).
                                </p>
                            </div>

                            <!-- Min count (nombre) -->
                            <div class="flex items-center gap-2">
                                <label class="text-xs text-gray-500">Nombre minimal :</label>
                                <input v-model.number="t.min_count" type="number" min="0"
                                    class="w-24 border rounded px-2 py-1" />
                            </div>

                            <!-- Actions par ligne -->
                            <div class="flex items-center gap-2">
                                <button class="p-2 rounded-full border bg-white hover:bg-red-50" title="Supprimer"
                                    @click="removeTask(i)">
                                    <TrashIcon class="w-5 h-5" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </template>
        </draggable>
    </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api/http'
import { useUserChallenge } from '@/composables/useUserChallenge'
import draggable from 'vuedraggable'
import {
    ArrowLeftIcon,
    PlusIcon,
    TrashIcon,
    Bars3Icon,
    ClipboardDocumentCheckIcon, // validate
    ArrowUpOnSquareIcon,        // save
} from '@heroicons/vue/24/outline'
import { inject } from 'vue'
import { CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/vue/24/solid'
const toast = inject<any>('toast')

type TaskExpr = any
type Task = {
    id?: string
    title: string
    expression: TaskExpr | null
    constraints: Record<string, any>
    status?: string | null
}

// UI-only: champs éditables
type TaskUI = Task & {
    expression_json: string     // texte du textarea
    min_count: number | null    // pour constraints.min_count
}

type ProgressRes = {
    evaluated_count: number
    skipped_count: number
    uc_ids: string[]
}


const tasks = ref<TaskUI[]>([])

const route = useRoute()
const router = useRouter()
const ucId = route.params.id as string
const { uc, safeDescription, fetchDetail } = useUserChallenge(ucId)

const loading = ref(false)
const error = ref<string | null>(null)
const rawMode = ref(false) // bascule JSON brut pour expression

async function fetchTasks() {
    loading.value = true
    error.value = null
    try {
        const { data } = await api.get(`/my/challenges/${ucId}/tasks`)
        const serverTasks: Task[] = (data?.tasks ?? []) as Task[]

        tasks.value = serverTasks.map((t) => {
            const exprStr = t.expression ? JSON.stringify(t.expression, null, 2) : ''
            const minCount = typeof t.constraints?.min_count === 'number' ? t.constraints.min_count : null
            return {
                ...t,
                expression_json: exprStr,
                min_count: minCount,
                constraints: t.constraints ?? {},
            }
        })
    } catch (e: any) {
        error.value = e?.message ?? 'Erreur de chargement'
    } finally {
        loading.value = false
    }
}

function addTask() {
    const defaultExpr = {
        kind: 'size_in',
        sizes: [{ code: 'L' }],
    }
    tasks.value.push({
        title: 'Nouvelle tâche',
        expression: defaultExpr,
        expression_json: JSON.stringify(defaultExpr, null, 2),
        min_count: 1,
        constraints: { min_count: 1 },
        status: 'todo',
    })
}

function removeTask(i: number) {
    tasks.value.splice(i, 1)
}

function buildPayload() {
    const out = tasks.value.map((t, i) => {
        let parsed: any = null
        // tenter de parser le JSON tapé
        try {
            parsed = t.expression_json ? JSON.parse(t.expression_json) : null
        } catch {
            // on laisse parsed=null → validation backend plantera, on remonte l’erreur
        }

        return {
            id: t.id,
            title: t.title || `Task #${i + 1}`,
            expression: parsed,                      // <— requis
            constraints: { min_count: t.min_count ?? 0 },  // <— objet simple
            status: t.status ?? 'todo',
        }
    })
    return { tasks: out }
}

function mapServerTasksToUI(serverTasks: any[]) {
    return (serverTasks ?? []).map((t) => {
        const exprStr = t.expression ? JSON.stringify(t.expression, null, 2) : ''
        const minCount = typeof t.constraints?.min_count === 'number' ? t.constraints.min_count : null
        return {
            ...t,
            expression_json: exprStr,
            min_count: minCount,
            constraints: t.constraints ?? {},
        }
    })
}

async function validateAll() {
    loading.value = true
    error.value = null
    try {
        const payload = buildPayload()
        await api.post(`/my/challenges/${ucId}/tasks/validate`, payload)
        toast?.value?.showToast('Validation réussie', CheckCircleIcon)
    } catch (e: any) {
        error.value = e?.response?.data?.detail ?? e?.message ?? 'Validation invalide'
        toast?.value?.showToast('Erreur de validation', ExclamationTriangleIcon)
    } finally {
        loading.value = false
    }
}

async function saveAll() {
    loading.value = true
    error.value = null
    try {
        const payload = buildPayload()
        // 1) Enregistrer
        const { data } = await api.put(`/my/challenges/${ucId}/tasks`, payload)

        // 2) Mettre à jour la liste locale si le backend renvoie tasks
        if (data?.tasks) {
            tasks.value = mapServerTasksToUI(data.tasks)
            console.log(tasks)
        }



        // 3) Recalcul du progrès pour ce seul UC
        //const { data: progress } = await api.post<ProgressRes>(`/my/challenges/new/progress`)

        // 4) Toast succès avec le récap
        //const msg = `Progrès recalculé: évalués ${progress.evaluated_count}, ignorés ${progress.skipped_count}`
        //toast?.value?.showToast(`Tâches enregistrées — ${msg}`, CheckCircleIcon)

    } catch (e: any) {
        error.value = e?.response?.data?.detail ?? e?.message ?? 'Erreur enregistrement'
    } finally {
        loading.value = false
    }
}

onMounted(async () => {
    await Promise.all([fetchDetail(), fetchTasks()])
})
</script>

<style scoped>
/* rien de spécial, Tailwind fait le job */
</style>
