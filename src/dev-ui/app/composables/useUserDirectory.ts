import type { UserProfileResponse } from '~/types'

/**
 * Session-scoped user identity resolution with batch fetching and caching.
 *
 * Resolves user UUIDs to display names via GET /iam/users?ids=...
 * Cache is invalidated on tenant switch.
 */
export function useUserDirectory() {
  const { lookupUsers } = useIamApi()
  const { tenantVersion } = useTenant()

  // In-memory cache: userId -> profile
  const cache = ref<Map<string, UserProfileResponse>>(new Map())

  // Invalidate cache on tenant switch
  watch(tenantVersion, () => {
    cache.value = new Map()
  })

  /**
   * Batch-resolve user IDs. Returns immediately for cached entries,
   * fetches missing ones from the API.
   */
  async function resolveUsers(userIds: string[]): Promise<void> {
    const uncached = userIds.filter((id) => !cache.value.has(id))
    if (uncached.length === 0) return

    try {
      const result = await lookupUsers(uncached)
      for (const user of result.users) {
        cache.value.set(user.id, user)
      }
    } catch {
      // Silently fail — unresolved IDs will show raw UUIDs
    }
  }

  /**
   * Get display name for a user ID.
   * Returns name (preferred) > username > raw userId.
   */
  function getDisplayName(userId: string): string {
    const profile = cache.value.get(userId)
    if (!profile) return userId
    return profile.name || profile.username
  }

  /**
   * Get the full cached profile for a user ID, if available.
   */
  function getProfile(userId: string): UserProfileResponse | undefined {
    return cache.value.get(userId)
  }

  return { resolveUsers, getDisplayName, getProfile, cache }
}
