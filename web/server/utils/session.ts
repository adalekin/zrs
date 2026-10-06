import type { H3Event } from 'h3'
import { getToken } from '#auth'
import { useSettings } from './settings'

/** The content of the session cookie, or null for a visitor without a session. */
export function readSessionToken(event: H3Event) {
  // The secret is passed explicitly: the auth module learns it only when its own route
  // is loaded, and that may happen after the first page request.
  return getToken({ event, secret: useSettings().authSecret })
}
