import { appendResponseHeader, defineEventHandler, getQuery, getRequestHeader, sendRedirect } from 'h3'
import { PROVIDER_ID } from '../utils/auth-options'
import { cookiesAfter } from '../utils/cookies'

interface AuthAnswer<T> {
  _data?: T
  headers: Headers
}

// Calls a route of this app in-process. `$fetch` infers its result from the routes of
// the app; the answers of next-auth are typed here instead.
const callAuth = $fetch.raw as <T>(url: string, options: object) => Promise<AuthAnswer<T>>

/**
 * Starts the sign-in at the provider and returns the person to `callbackUrl` afterwards.
 *
 * next-auth starts a sign-in only on a POST that carries its CSRF token, so the route
 * makes the two calls that a browser client of next-auth makes, and hands the cookies
 * they set (CSRF, state, PKCE verifier, callback address) to the browser.
 */
export default defineEventHandler(async (event) => {
  const { callbackUrl } = getQuery(event)
  const browserCookies = getRequestHeader(event, 'cookie')

  const csrf = await callAuth<{ csrfToken: string }>('/api/auth/csrf', {
    headers: browserCookies ? { cookie: browserCookies } : {},
  })
  const csrfCookies = csrf.headers.getSetCookie()

  const signIn = await callAuth<{ url: string }>(`/api/auth/signin/${PROVIDER_ID}`, {
    method: 'POST',
    headers: {
      'content-type': 'application/x-www-form-urlencoded',
      'cookie': cookiesAfter(browserCookies, csrfCookies),
    },
    body: new URLSearchParams({
      csrfToken: csrf._data!.csrfToken,
      // Opened without a page to return to: return to the list of requests.
      callbackUrl: typeof callbackUrl === 'string' ? callbackUrl : '/',
      json: 'true',
    }).toString(),
  })

  for (const cookie of [...csrfCookies, ...signIn.headers.getSetCookie()]) {
    appendResponseHeader(event, 'set-cookie', cookie)
  }
  // The address of the provider, or the error page of next-auth when the provider
  // cannot be reached.
  return sendRedirect(event, signIn._data!.url)
})
