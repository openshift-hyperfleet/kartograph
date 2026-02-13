import { toast } from 'vue-sonner'
import type { TenantResponse } from '~/types'

const STORAGE_KEY = 'kartograph:current-tenant'

/**
 * Centralised tenant state composable.
 *
 * Manages the currently-selected tenant across the whole application.
 * The selected tenant ID is persisted in localStorage so it survives
 * page refreshes and is exposed via Nuxt `useState` so every component
 * and composable (including `useApiClient`) shares the same reactive ref.
 *
 * A monotonically-increasing `tenantVersion` counter is bumped on every
 * tenant switch.  Tenant-scoped pages watch this counter and re-fetch
 * their data automatically.
 */
export function useTenant() {
  // The canonical tenant ID — shared app-wide via useState
  const currentTenantId = useState<string | null>('tenant:current', () => null)

  // Bumped on every tenant switch so watchers can trigger re-fetches
  const tenantVersion = useState<number>('tenant:version', () => 0)

  // Tenant list & loading state (populated by the layout)
  const tenants = useState<TenantResponse[]>('tenant:list', () => [])
  const tenantsLoading = useState<boolean>('tenant:loading', () => false)
  const tenantsLoaded = useState<boolean>('tenant:loaded', () => false)

  /**
   * Restore the previously-selected tenant from localStorage.
   * Called once during app initialisation (in the layout).
   */
  function restoreFromStorage(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem(STORAGE_KEY)
  }

  /**
   * Persist the current tenant ID to localStorage.
   */
  function persistToStorage(id: string | null) {
    if (typeof window === 'undefined') return
    if (id) {
      localStorage.setItem(STORAGE_KEY, id)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  /**
   * Switch to a different tenant.  Updates persistent storage, the
   * shared state, and bumps `tenantVersion` so watchers re-fetch.
   *
   * @param id   The tenant ID to switch to.
   * @param name Optional tenant name for the toast notification.
   */
  function switchTenant(id: string, name?: string) {
    if (id === currentTenantId.value) return

    currentTenantId.value = id
    persistToStorage(id)
    tenantVersion.value++

    if (name) {
      toast.success('Tenant switched', {
        description: `Now viewing data for "${name}".`,
      })
    }
  }

  /**
   * Called after the tenant list is fetched.  Handles auto-selection:
   * 1. If a tenant was previously persisted, re-select it (if still valid).
   * 2. Otherwise auto-select the first tenant.
   * 3. If the list is empty, clear the selection.
   */
  function reconcileAfterFetch(fetchedTenants: TenantResponse[]) {
    tenants.value = fetchedTenants
    tenantsLoaded.value = true

    if (fetchedTenants.length === 0) {
      currentTenantId.value = null
      persistToStorage(null)
      return
    }

    const stored = restoreFromStorage()
    const stillValid = stored && fetchedTenants.some((t) => t.id === stored)

    if (stillValid) {
      // Silently restore — no toast, user expects continuity
      currentTenantId.value = stored
    } else {
      // Auto-select first tenant
      const first = fetchedTenants[0]
      currentTenantId.value = first.id
      persistToStorage(first.id)
    }
  }

  /**
   * Called when the currently-selected tenant is deleted elsewhere in the
   * UI (e.g. on the Tenants management page).  Falls back to the first
   * remaining tenant or clears selection.
   */
  function handleCurrentTenantDeleted() {
    const remaining = tenants.value.filter((t) => t.id !== currentTenantId.value)
    tenants.value = remaining

    if (remaining.length > 0) {
      switchTenant(remaining[0].id, remaining[0].name)
    } else {
      currentTenantId.value = null
      persistToStorage(null)
      tenantVersion.value++
    }
  }

  /**
   * Look up the display name for the current tenant.
   */
  const currentTenantName = computed(() => {
    if (!currentTenantId.value) return null
    return tenants.value.find((t) => t.id === currentTenantId.value)?.name ?? null
  })

  /**
   * True when a tenant is selected and ready for API calls.
   */
  const hasTenant = computed(() => !!currentTenantId.value)

  /**
   * Update the shared tenant list without changing the selection.
   * Used when the tenants management page creates or deletes tenants
   * and needs the header dropdown to stay in sync.
   */
  function syncTenantList(updatedTenants: TenantResponse[]) {
    tenants.value = updatedTenants
  }

  return {
    currentTenantId,
    currentTenantName,
    tenants,
    tenantsLoading,
    tenantsLoaded,
    tenantVersion,
    hasTenant,
    switchTenant,
    reconcileAfterFetch,
    handleCurrentTenantDeleted,
    syncTenantList,
    restoreFromStorage,
    persistToStorage,
  }
}
