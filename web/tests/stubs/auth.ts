import type { IncomingHttpHeaders } from 'node:http'
import type { H3Event } from 'h3'
import { getHeaders, parseCookies } from 'h3'
import { getToken as nextAuthGetToken } from 'next-auth/jwt'

/**
 * Stands in for `getToken` of `#auth`: like the module, it hands the cookies of the h3
 * event to `getToken` of next-auth, so the tests decode real session cookies.
 */
export function getToken({ event, secret }: { event: H3Event, secret: string }) {
  return nextAuthGetToken({
    // @ts-expect-error next-auth reads only the cookies and the headers of the request
    req: { cookies: parseCookies(event), headers: getHeaders(event) as IncomingHttpHeaders },
    secret,
  })
}
