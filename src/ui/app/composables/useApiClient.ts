import type { NitroFetchOptions } from 'nitropack'

/**
 * Provides a pre-configured `$fetch` wrapper that automatically attaches:
 *  - Bearer token from the current OIDC session
 *  - X-Tenant-ID header from the current tenant context
 *  - Base URL from runtime config
 */
export function useApiClient() {
  const config = useRuntimeConfig()
  const { accessToken } = useAuth()
  const currentTenantId = useState<string | null>('tenant:current', () => null)

  /**
   * A thin wrapper around Nuxt's global `$fetch` that injects auth &
   * tenant headers. All bounded-context API modules delegate to this.
   */
  async function apiFetch<T>(
    path: string,
    opts: NitroFetchOptions<string> = {},
  ): Promise<T> {
    const headers: Record<string, string> = {
      ...(opts.headers as Record<string, string> ?? {}),
    }

    if (accessToken.value) {
      headers['Authorization'] = `Bearer ${accessToken.value}`
    }

    if (currentTenantId.value) {
      headers['X-Tenant-ID'] = currentTenantId.value
    }

    return $fetch<T>(path, {
      baseURL: config.public.apiBaseUrl as string,
      ...opts,
      headers,
    })
  }

  return {
    apiFetch,
    currentTenantId,
  }
}
