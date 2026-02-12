<script setup lang="ts">
const { handleCallback } = useAuth()
const router = useRouter()

onMounted(async () => {
  try {
    await handleCallback()
    await router.replace('/')
  } catch (err) {
    console.error('[auth/callback] OIDC callback failed', err)
    // If the callback fails (e.g. stale state), restart the login flow.
    const { login } = useAuth()
    await login()
  }
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center">
    <p class="text-muted-foreground">Signing in…</p>
  </div>
</template>
