<script setup lang="ts">
import { Toaster } from '@/components/ui/sonner'
import MutationProgress from '@/components/graph/MutationProgress.vue'
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <MutationProgress />
  <Toaster richColors :duration="10000" position="bottom-right" />
</template>
