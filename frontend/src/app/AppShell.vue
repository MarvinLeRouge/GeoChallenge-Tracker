<template>
  <div class="min-h-screen flex">
    <!-- SideNav -->
    <aside class="w-56 border-r hidden md:block">
      <nav class="p-4 space-y-2">
        <RouterLink to="/" class="block hover:underline">Accueil</RouterLink>
      </nav>
    </aside>

    <!-- Content -->
    <div class="flex-1 flex flex-col">
      <header class="h-12 border-b flex items-center px-4 justify-between">
        <h1 class="font-semibold">GeoChallenge Tracker</h1>
      </header>
      <main class="p-4">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
/* Rien de spécial pour l’instant */
</script>
