/**
 * Global auth middleware.
 *
 * Runs before every route navigation. If the user is not authenticated
 * (and is not already on the callback page) we redirect them to Keycloak.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  // Always allow the callback page through – it needs to process the
  // authorization code before we have a session.
  if (to.path === '/auth/callback') {
    return
  }

  const { isAuthenticated, initialize, login } = useAuth()

  // On the first navigation the reactive state is empty – try to restore
  // a session from sessionStorage before deciding.
  if (!isAuthenticated.value) {
    await initialize()
  }

  if (!isAuthenticated.value) {
    // Not authenticated – kick off the Keycloak login redirect.
    // Return `false` to abort the current navigation; the redirect will
    // navigate the browser to an external URL.
    await login()
    return abortNavigation()
  }
})
