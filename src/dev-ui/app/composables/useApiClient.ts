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
    const headers: Record<string, string> = {}

    // Normalize incoming headers to a plain object
    if (opts.headers) {
      if (opts.headers instanceof Headers) {
        opts.headers.forEach((value, key) => {
          headers[key] = value
        })
      } else if (Array.isArray(opts.headers)) {
        for (const [key, value] of opts.headers) {
          headers[key] = value
        }
      } else {
        Object.assign(headers, opts.headers)
      }
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
