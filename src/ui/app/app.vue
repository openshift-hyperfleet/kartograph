<script setup lang="ts">
import { Toaster } from '@/components/ui/sonner'
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <Toaster richColors :duration="5000" position="bottom-right" />
</template>
