import type { H3Event } from 'h3'
import { getProxyRequestHeaders, getRequestWebStream, sendProxy, setResponseStatus } from 'h3'

const METHODS_WITH_BODY = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

/**
 * Forwards a browser request for /api/v1/** to the server as /v1/**, with the access
 * token of the session. Method, query, body and the response pass through unchanged.
 */
export async function proxyToApi(event: H3Event, apiUrl: string, accessToken: string | undefined) {
  if (!accessToken) {
    setResponseStatus(event, 401)
    return { detail: 'Not authenticated' }
  }

  const target = new URL(apiUrl + event.path.slice('/api'.length))
  // Dot segments are resolved by now: the request must still point inside /v1/.
  if (!target.href.startsWith(new URL(`${apiUrl}/v1/`).href)) {
    setResponseStatus(event, 404)
    return { detail: 'Not found' }
  }

  const headers = getProxyRequestHeaders(event)
  // The session cookie holds the tokens and stays in the web app.
  delete headers.cookie
  headers.authorization = `Bearer ${accessToken}`

  const hasBody = METHODS_WITH_BODY.has(event.method)
  return sendProxy(event, target.href, {
    fetchOptions: {
      method: event.method,
      headers,
      body: hasBody ? getRequestWebStream(event) : undefined,
      duplex: hasBody ? 'half' : undefined,
    },
  })
}
