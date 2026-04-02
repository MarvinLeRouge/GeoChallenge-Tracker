<template>
  <div class="space-y-4 max-w-sm">
    <h2 class="text-xl font-semibold">Vérification de l'adresse e-mail</h2>

    <p v-if="status === 'pending'" class="text-sm text-gray-500">
      Vérification en cours…
    </p>

    <p v-else-if="status === 'success'" class="text-sm text-green-600">
      Votre adresse e-mail a bien été vérifiée. Vous pouvez maintenant vous
      connecter.
    </p>

    <p v-else-if="status === 'error'" class="text-sm text-red-600">
      {{ error }}
    </p>

    <router-link
      v-if="status !== 'pending'"
      :to="{ name: 'auth/login' }"
      class="inline-block border px-3 py-2 text-sm"
    >
      Se connecter
    </router-link>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import api from "@/api/http";

type Status = "pending" | "success" | "error";

const route = useRoute();
const status = ref<Status>("pending");
const error = ref("");

onMounted(async () => {
  const code = route.query.code as string | undefined;

  if (!code) {
    status.value = "error";
    error.value = "Lien de vérification invalide ou incomplet.";
    return;
  }

  try {
    await api.get("/auth/verify-email", { params: { code } });
    status.value = "success";
  } catch (e: unknown) {
    status.value = "error";
    const msg = (e as { response?: { data?: { detail?: string } } })?.response
      ?.data?.detail;
    error.value = msg ?? "Le lien est invalide ou a expiré.";
  }
});
</script>
