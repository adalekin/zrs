import type { Settings } from './settings'

/** The tokens of a signed-in person. They live in the encrypted session cookie only. */
export interface TokenSet {
  accessToken: string
  /** Absent when the provider issues no refresh token: the session then ends with the access token. */
  refreshToken?: string
  idToken: string
  /** Expiry of the access token, in seconds since the epoch. */
  expiresAt: number
}

/** The provider answered in a way that OpenID Connect does not allow, or refused the request. */
export class OidcError extends Error {}

interface Discovery {
  token_endpoint: string
  end_session_endpoint?: string
}

const discoveries = new Map<string, Promise<Discovery>>()

/** The discovery document of the provider, fetched once per process. */
export function discover(issuer: string): Promise<Discovery> {
  let pending = discoveries.get(issuer)
  if (!pending) {
    pending = fetchDiscovery(issuer)
    // A failed fetch is not kept: the next call asks the provider again.
    pending.catch(() => discoveries.delete(issuer))
    discoveries.set(issuer, pending)
  }
  return pending
}

async function fetchDiscovery(issuer: string): Promise<Discovery> {
  const url = `${issuer}/.well-known/openid-configuration`
  const response = await fetch(url)
  if (!response.ok) {
    throw new OidcError(`Discovery document ${url} answered HTTP ${response.status}`)
  }
  const document = await response.json() as Partial<Discovery>
  if (typeof document.token_endpoint !== 'string') {
    throw new OidcError(`Discovery document ${url} has no token_endpoint`)
  }
  return document as Discovery
}

// RFC 6749, section 2.3.1: the client id and secret are form-encoded before Basic encoding.
function formEncode(value: string): string {
  return new URLSearchParams({ v: value }).toString().slice(2)
}

async function requestRefresh(settings: Settings, tokens: TokenSet): Promise<TokenSet> {
  if (!tokens.refreshToken) {
    throw new OidcError('The session has no refresh token')
  }

  const { token_endpoint } = await discover(settings.oidcIssuer)
  const credentials = `${formEncode(settings.oidcClientId)}:${formEncode(settings.oidcClientSecret)}`
  const response = await fetch(token_endpoint, {
    method: 'POST',
    headers: {
      'content-type': 'application/x-www-form-urlencoded',
      'authorization': `Basic ${Buffer.from(credentials).toString('base64')}`,
    },
    body: new URLSearchParams({ grant_type: 'refresh_token', refresh_token: tokens.refreshToken }),
  })
  if (!response.ok) {
    throw new OidcError(`The provider refused to refresh the access token: HTTP ${response.status}`)
  }

  const body = await response.json() as Record<string, unknown>
  if (typeof body.access_token !== 'string' || typeof body.expires_in !== 'number') {
    throw new OidcError('The refresh response has no access_token or expires_in')
  }

  return {
    accessToken: body.access_token,
    expiresAt: Math.floor(Date.now() / 1000) + body.expires_in,
    // RFC 6749, section 6, and OpenID Connect Core, section 12.2: a refresh response may
    // carry a new refresh token and a new ID token; when it does not, the old ones stay.
    refreshToken: typeof body.refresh_token === 'string' ? body.refresh_token : tokens.refreshToken,
    idToken: typeof body.id_token === 'string' ? body.id_token : tokens.idToken,
  }
}

const REFRESH_RESULT_KEPT_MS = 10_000
const refreshes = new Map<string, Promise<TokenSet>>()

/**
 * Exchanges the refresh token for a new access token.
 *
 * Requests that carry the same refresh token share one exchange, and its result is kept
 * for a few seconds: a browser may send several requests with the old session cookie
 * before the new one reaches it, and a provider that rotates refresh tokens accepts
 * each of them once.
 */
export function refreshTokens(settings: Settings, tokens: TokenSet): Promise<TokenSet> {
  const key = `${settings.oidcIssuer} ${tokens.refreshToken}`
  let pending = refreshes.get(key)
  if (!pending) {
    pending = requestRefresh(settings, tokens)
    const forget = () => {
      setTimeout(() => refreshes.delete(key), REFRESH_RESULT_KEPT_MS).unref()
    }
    pending.then(forget, forget)
    refreshes.set(key, pending)
  }
  return pending
}

/**
 * The address that ends the session at the provider and returns the person to the app
 * (OpenID Connect RP-Initiated Logout 1.0).
 */
export async function endSessionUrl(settings: Settings, idToken: string): Promise<string> {
  const { end_session_endpoint } = await discover(settings.oidcIssuer)
  if (typeof end_session_endpoint !== 'string') {
    throw new OidcError('The discovery document of the provider has no end_session_endpoint')
  }

  const url = new URL(end_session_endpoint)
  url.searchParams.set('id_token_hint', idToken)
  url.searchParams.set('client_id', settings.oidcClientId)
  url.searchParams.set('post_logout_redirect_uri', `${settings.authOrigin}/`)
  return url.href
}
