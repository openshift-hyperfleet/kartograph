<script setup lang="ts">
import { UserManager } from 'oidc-client-ts'

definePageMeta({ layout: false })

onMounted(() => {
  new UserManager({ response_mode: 'query' }).signinSilentCallback()
})
</script>

<template>
  <div />
</template>
