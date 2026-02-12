<script setup lang="ts">
const { handleCallback } = useAuth()
const router = useRouter()
const timedOut = ref(false)

onMounted(async () => {
  const timer = setTimeout(() => {
    timedOut.value = true
  }, 15000)

  try {
    await handleCallback()
    clearTimeout(timer)
    await router.replace('/')
  } catch (err) {
    clearTimeout(timer)
    console.warn('[auth/callback] OIDC callback failed', err)
    // If the callback fails (e.g. stale state), restart the login flow.
    const { login } = useAuth()
    await login()
  }
})

async function retryLogin() {
  const { login } = useAuth()
  await login()
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center">
    <div v-if="timedOut" class="flex flex-col items-center gap-4 text-center">
      <p class="text-muted-foreground">Sign-in is taking longer than expected.</p>
      <Button variant="outline" @click="retryLogin">Try again</Button>
    </div>
    <p v-else class="text-muted-foreground">Signing in...</p>
  </div>
</template>
