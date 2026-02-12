/**
 * Extract a human-readable error message from API errors.
 * Nuxt's $fetch throws FetchError which includes response data.
 */
export function useErrorHandler() {
  function extractErrorMessage(err: unknown): string {
    if (err && typeof err === 'object') {
      // Nuxt $fetch FetchError - has response data
      const fetchErr = err as { data?: { detail?: string; message?: string }; statusCode?: number; message?: string }
      if (fetchErr.data?.detail) {
        // FastAPI returns { detail: "..." } for HTTP errors
        if (typeof fetchErr.data.detail === 'string') return fetchErr.data.detail
        // Sometimes detail is an array of validation errors
        if (Array.isArray(fetchErr.data.detail)) {
          return fetchErr.data.detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join('; ')
        }
        return JSON.stringify(fetchErr.data.detail)
      }
      if (fetchErr.data?.message) return fetchErr.data.message
      if (fetchErr.statusCode) return `Request failed with status ${fetchErr.statusCode}`
      if (fetchErr.message) return fetchErr.message
    }
    if (err instanceof Error) return err.message
    return 'An unexpected error occurred'
  }

  return { extractErrorMessage }
}
