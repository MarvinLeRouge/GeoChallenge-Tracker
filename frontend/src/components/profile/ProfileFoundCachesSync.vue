<template>
  <!-- Synchronisation des found caches -->
  <div
    class="bg-white rounded-lg border border-gray-200 p-6 dark:bg-gray-800 dark:border-gray-700"
  >
    <h3
      class="text-lg font-medium text-gray-900 mb-4 flex items-center dark:text-gray-100"
    >
      <ArrowPathIcon class="h-5 w-5 mr-2 text-gray-600 dark:text-gray-400" />
      Synchronisation des found caches
    </h3>

    <div
      class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4 dark:bg-blue-950 dark:border-blue-900"
    >
      <div class="flex">
        <InformationCircleIcon
          class="h-5 w-5 text-blue-400 mt-0.5 shrink-0 dark:text-blue-500"
        />
        <p class="ml-3 text-sm text-blue-700 dark:text-blue-300">
          Fournissez un fichier (texte, GPX, JSON…) contenant vos codes GC.
          Cette liste sera traitée comme la liste complète et définitive de vos
          found caches : les entrées absentes seront supprimées, les nouvelles
          ajoutées.
        </p>
      </div>
    </div>

    <!-- Drop zone / file input -->
    <label
      class="flex flex-col items-center justify-center w-full h-28 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition dark:border-gray-600 dark:hover:bg-gray-700"
      :class="{
        'border-indigo-400 bg-indigo-50 dark:bg-indigo-950': syncDragOver,
      }"
      @dragover.prevent="syncDragOver = true"
      @dragleave.prevent="syncDragOver = false"
      @drop.prevent="onSyncDrop"
    >
      <DocumentArrowUpIcon
        class="h-8 w-8 text-gray-400 mb-1 dark:text-gray-500"
      />
      <span class="text-sm text-gray-500 dark:text-gray-400">
        {{
          syncFile
            ? syncFile.name
            : "Glissez un fichier ou cliquez pour choisir"
        }}
      </span>
      <input
        ref="syncFileInput"
        type="file"
        class="hidden"
        @change="onSyncFileChange"
      />
    </label>

    <div class="mt-3 flex items-center gap-3">
      <button
        type="button"
        :disabled="!syncFile || syncLoading"
        class="flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        @click="submitSync"
      >
        <span
          v-if="syncLoading"
          class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"
        />
        {{ syncLoading ? "Synchronisation…" : "Synchroniser" }}
      </button>
      <span v-if="syncFile" class="text-xs text-gray-500 dark:text-gray-400">{{
        syncFile.name
      }}</span>
    </div>

    <!-- Result -->
    <div
      v-if="syncResult"
      class="mt-4 rounded-lg border p-4 space-y-1 text-sm"
      :class="
        syncResult.nb_unknown_gc > 0
          ? 'border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950'
          : 'border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950'
      "
    >
      <p>
        <span class="font-medium">Codes GC fournis :</span>
        {{ syncResult.nb_provided }}
      </p>
      <p>
        <span class="font-medium">Ajoutés :</span> {{ syncResult.nb_added }}
      </p>
      <p>
        <span class="font-medium">Supprimés :</span>
        {{ syncResult.nb_deleted }}
      </p>
      <p>
        <span class="font-medium">Codes inconnus :</span>
        {{ syncResult.nb_unknown_gc }}
        <span
          v-if="syncResult.nb_unknown_gc > 0"
          class="text-yellow-700 dark:text-yellow-400"
        >
          — importez un GPX pour les ajouter à la base
        </span>
      </p>
      <div v-if="syncResult.unknown_gc_codes.length > 0" class="mt-2">
        <p class="font-medium text-yellow-800 mb-1 dark:text-yellow-300">
          Codes non reconnus :
        </p>
        <p
          class="font-mono text-xs text-yellow-700 break-all dark:text-yellow-400"
        >
          {{ syncResult.unknown_gc_codes.join(", ") }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import {
  ArrowPathIcon,
  InformationCircleIcon,
  DocumentArrowUpIcon,
} from "@heroicons/vue/24/outline";
import api from "@/api/http";
import { toast } from "vue-sonner";

interface SyncResult {
  nb_provided: number;
  nb_added: number;
  nb_deleted: number;
  nb_unknown_gc: number;
  unknown_gc_codes: string[];
}

const syncFile = ref<File | null>(null);
const syncLoading = ref(false);
const syncResult = ref<SyncResult | null>(null);
const syncDragOver = ref(false);
const syncFileInput = ref<HTMLInputElement | null>(null);

function onSyncFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  syncFile.value = input.files?.[0] ?? null;
  syncResult.value = null;
}

function onSyncDrop(e: DragEvent) {
  syncDragOver.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file) {
    syncFile.value = file;
    syncResult.value = null;
  }
}

async function submitSync() {
  if (!syncFile.value) return;
  syncLoading.value = true;
  syncResult.value = null;
  try {
    const form = new FormData();
    form.append("file", syncFile.value);
    const { data } = await api.post<SyncResult>(
      "/my/profile/found-caches/sync",
      form,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    syncResult.value = data;
    toast.success("Synchronisation effectuée", {
      description: `${data.nb_added} ajouté(s), ${data.nb_deleted} supprimé(s)`,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    toast.error("Erreur lors de la synchronisation", { description: msg });
  } finally {
    syncLoading.value = false;
  }
}
</script>
