import { UserManager, WebStorageStateStore, type User } from 'oidc-client-ts'

/**
 * Keycloak OIDC composable using Authorization Code + PKCE via oidc-client-ts.
 *
 * The UserManager handles token refresh automatically through its
 * `automaticSilentRenew` setting which fires a silent token refresh
 * before the access token expires.
 */
/**
 * Module-level singleton for the UserManager.
 * Shared across all invocations of useAuth() via Nuxt's auto-import
 * module caching. This ensures only one UserManager instance exists.
 */
let _manager: UserManager | undefined

export function useAuth() {
  const config = useRuntimeConfig()
  const kc = config.public.keycloak as {
    url: string
    realm: string
    clientId: string
  }

  // Shared reactive state across the app via Nuxt useState
  const user = useState<User | null>('auth:user', () => null)

  const isAuthenticated = computed(() => !!user.value && !user.value.expired)
  const accessToken = computed(() => user.value?.access_token ?? null)

  function getManager(): UserManager {
    if (_manager) return _manager

    const authority = `${kc.url}/realms/${kc.realm}`

    _manager = new UserManager({
      authority,
      client_id: kc.clientId,
      redirect_uri: `${window.location.origin}/auth/callback`,
      post_logout_redirect_uri: window.location.origin,
      response_type: 'code',
      scope: 'openid profile email',

      // Explicit endpoint overrides – avoids an extra discovery request when
      // the Keycloak instance is on a different host/port from the UI and
      // CORS on the well-known endpoint may not be configured yet during dev.
      metadata: {
        issuer: authority,
        authorization_endpoint: `${authority}/protocol/openid-connect/auth`,
        token_endpoint: `${authority}/protocol/openid-connect/token`,
        end_session_endpoint: `${authority}/protocol/openid-connect/logout`,
        userinfo_endpoint: `${authority}/protocol/openid-connect/userinfo`,
        jwks_uri: `${authority}/protocol/openid-connect/certs`,
      },

      // PKCE is enabled by default in oidc-client-ts when response_type is 'code'
      automaticSilentRenew: true,
      silentRequestTimeoutInSeconds: 10,
      userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    })

    // Keep the reactive state in sync whenever the user object changes
    _manager.events.addUserLoaded((loaded) => {
      user.value = loaded
    })

    _manager.events.addUserUnloaded(() => {
      user.value = null
    })

    _manager.events.addSilentRenewError((err) => {
      console.error('[auth] silent renew failed', err)
    })

    return _manager
  }

  /** Redirect the browser to Keycloak's login page. */
  async function login(): Promise<void> {
    await getManager().signinRedirect()
  }

  /** Handle the OIDC callback redirect – exchanges the auth code for tokens. */
  async function handleCallback(): Promise<User> {
    const mgr = getManager()
    const loaded = await mgr.signinRedirectCallback()
    user.value = loaded
    return loaded
  }

  /** Check sessionStorage for an existing (non-expired) session. */
  async function initialize(): Promise<void> {
    const mgr = getManager()
    const existing = await mgr.getUser()
    if (existing && !existing.expired) {
      user.value = existing
    }
  }

  /** Redirect the browser to Keycloak's logout page. */
  async function logout(): Promise<void> {
    const mgr = getManager()
    user.value = null
    await mgr.signoutRedirect()
  }

  return {
    user,
    isAuthenticated,
    accessToken,
    login,
    logout,
    handleCallback,
    initialize,
  }
}
