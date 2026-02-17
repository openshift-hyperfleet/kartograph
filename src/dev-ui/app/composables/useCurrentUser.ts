/**
 * Composable that exposes the current authenticated user's identity.
 *
 * Wraps the OIDC profile claims from `useAuth()` in a convenient,
 * reusable API so consumers don't need to dig into
 * `useAuth().user.value.profile.sub` everywhere.
 */
export function useCurrentUser() {
  const { user } = useAuth()

  const userId = computed(() => user.value?.profile?.sub ?? '')

  const displayName = computed(() => {
    if (!user.value) return ''
    const p = user.value.profile
    return p?.preferred_username ?? p?.name ?? p?.email ?? ''
  })

  const email = computed(() => user.value?.profile?.email ?? '')

  /**
   * Returns `true` when the given id matches the current user's OIDC `sub` claim.
   */
  function isCurrentUser(id: string): boolean {
    return !!userId.value && id === userId.value
  }

  return { userId, displayName, email, isCurrentUser }
}
