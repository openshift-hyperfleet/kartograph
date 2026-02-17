/**
 * Extract a human-readable error message from API errors.
 * Nuxt's $fetch throws FetchError which includes response data.
 */
export function useErrorHandler() {
  function extractErrorMessage(err: unknown): string {
    if (err && typeof err === 'object') {
      // Nuxt $fetch FetchError - has response data
      const fetchErr = err as { data?: { detail?: unknown; message?: string }; statusCode?: number; message?: string }
      if (fetchErr.data?.detail !== undefined && fetchErr.data?.detail !== null) {
        const detail = fetchErr.data.detail
        // FastAPI returns { detail: "..." } for HTTP errors
        if (typeof detail === 'string') return detail
        // Sometimes detail is an array of validation errors
        if (Array.isArray(detail)) {
          return detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join('; ')
        }
        // detail can be an object like { errors: ["msg1", "msg2"] }
        if (typeof detail === 'object' && detail !== null) {
          const detailObj = detail as Record<string, unknown>
          if (Array.isArray(detailObj.errors)) {
            return detailObj.errors.map((e: unknown) =>
              typeof e === 'string' ? e : JSON.stringify(e),
            ).join('; ')
          }
        }
        return JSON.stringify(detail)
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
