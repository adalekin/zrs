import { defineEventHandler, getRequestHeader, sendRedirect, setResponseStatus } from 'h3'
import { SIGN_IN_PATH, signInLocation } from '../../shared/utils/sign-in'
import { readSessionToken } from '../utils/session'

/**
 * Every page requires a session. A visitor without one is sent to the sign-in page,
 * which starts the sign-in at the provider and returns them to the page they asked for.
 */
export default defineEventHandler(async (event) => {
  if (event.method !== 'GET' && event.method !== 'HEAD') {
    return
  }
  const pathname = event.path.split('?', 1)[0]!
  // API routes answer for themselves; paths that start with an underscore are assets
  // and internal routes of the framework.
  if (pathname.startsWith('/api/') || pathname.startsWith('/_') || pathname === SIGN_IN_PATH) {
    return
  }
  if (await readSessionToken(event)) {
    return
  }

  // Only a page navigation starts a sign-in: a second one, started by a stray request
  // of the same browser, would overwrite the state of the first.
  if (!getRequestHeader(event, 'accept')?.includes('text/html')) {
    setResponseStatus(event, 401)
    return { detail: 'Not authenticated' }
  }
  return sendRedirect(event, signInLocation(event.path))
})
