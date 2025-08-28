<template>
  <div class="min-h-screen flex flex-col items-center justify-center bg-gray-100 text-gray-800">
    <h1 class="text-2xl font-bold mb-4">🌐 Frontend is up</h1>
    <p v-if="message">✅ Backend says: {{ message }}</p>
    <p v-else>⏳ Contacting backend...</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
const message = ref('')

onMounted(async () => {
  try {
    const res = await fetch('/api/ping')
    console.log("res")
    const data = await res.text()
    message.value = data
  } catch (err) {
    message.value = '❌ Could not reach backend'
  }
})
</script>
