interface ApiOptions {
  method?: 'POST' | 'PATCH' | 'DELETE'
  query?: Record<string, string | number | boolean | undefined>
  body?: object
}

// `$fetch` infers its result from the routes of this app; the answers of the proxied
// server are typed by the caller instead.
const request = $fetch as (url: string, options?: ApiOptions) => Promise<unknown>

let sessionRead: Promise<unknown> | undefined

/**
 * Calls the server API through the /api/v1 route of this app, which adds the access
 * token of the session. The browser never talks to the server directly.
 */
export function useApi() {
  const { getSession, status } = useAuth()
  const route = useRoute()

  return async function api<T>(path: string, options?: ApiOptions): Promise<T> {
    const call = () => request(`/api/v1${path}`, options) as Promise<T>

    try {
      return await call()
    }
    catch (error) {
      if (apiStatus(error) !== 401) {
        throw error
      }
    }

    // The access token expired between two session reads. A session read renews it;
    // calls that failed together share one read.
    sessionRead ??= getSession().finally(() => {
      sessionRead = undefined
    })
    await sessionRead

    if (status.value === 'unauthenticated') {
      // The session has ended: sign in again and come back to this page.
      window.location.assign(signInLocation(route.fullPath))
    }
    // With a live session a second 401 is the server refusing the token, for example
    // one issued for another audience. A new sign-in would bring the same token, so
    // the call fails instead of sending the person round in circles.
    return await call()
  }
}
