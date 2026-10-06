import { defineEventHandler, deleteCookie, parseCookies, sendRedirect } from 'h3'
import { endSessionUrl } from '../utils/oidc'
import { readSessionToken } from '../utils/session'
import { useSettings } from '../utils/settings'

// The session cookie of next-auth, possibly split into numbered chunks.
const SESSION_COOKIE = /^(__Secure-)?next-auth\.session-token(\.\d+)?$/

/**
 * Sign-out: ends the session here and sends the browser to the provider to end the
 * session there. The provider returns the person to the app, which asks to sign in again.
 */
export default defineEventHandler(async (event) => {
  const token = await readSessionToken(event)
  if (!token) {
    return sendRedirect(event, '/', 303)
  }

  // Resolved before the cookie is removed: if the provider cannot end its session,
  // the request fails and the person stays signed in here as well.
  const providerUrl = await endSessionUrl(useSettings(), token.idToken)

  for (const name of Object.keys(parseCookies(event))) {
    if (SESSION_COOKIE.test(name)) {
      deleteCookie(event, name, { path: '/', secure: name.startsWith('__Secure-') })
    }
  }
  return sendRedirect(event, providerUrl, 303)
})
