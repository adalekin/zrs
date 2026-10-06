/**
 * The server lets a page request through when it carries a session cookie
 * (server/middleware/page-guard.ts). The session may still have ended: the provider
 * refused to renew the access token. Then the person signs in again.
 */
export default defineNuxtRouteMiddleware((to) => {
  const { status } = useAuth()
  if (status.value === 'unauthenticated') {
    // A route of the server, not a page of the app.
    return navigateTo(signInLocation(to.fullPath), { external: true })
  }
})
