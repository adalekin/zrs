import type { Server } from 'node:http'
import { decode } from 'next-auth/jwt'
import { AuthHandler } from 'next-auth/core'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { buildAuthOptions } from '../server/utils/auth-options'
import { readSettings } from '../server/utils/settings'
import { AUTH_SECRET, ENV, listen, readBody, sessionCookie } from './helpers'

const now = () => Math.floor(Date.now() / 1000)

interface TokenRequest {
  authorization?: string
  body: URLSearchParams
}

let provider: Server
let issuer: string
let tokenRequests: TokenRequest[]
let refuseRefresh = false

beforeAll(async () => {
  // Stands in for the identity provider: discovery document and token endpoint.
  const listening = await listen(async (req, res) => {
    res.setHeader('content-type', 'application/json')
    if (req.url === '/.well-known/openid-configuration') {
      res.end(JSON.stringify({ issuer, token_endpoint: `${issuer}/token` }))
    }
    else if (req.url === '/token' && refuseRefresh) {
      res.writeHead(400).end(JSON.stringify({ error: 'invalid_grant' }))
    }
    else if (req.url === '/token') {
      tokenRequests.push({
        authorization: req.headers.authorization,
        body: new URLSearchParams((await readBody(req)).toString()),
      })
      res.end(JSON.stringify({ access_token: 'renewed-access-token-value', expires_in: 300, token_type: 'Bearer' }))
    }
    else {
      res.writeHead(404).end('{}')
    }
  })
  provider = listening.server
  issuer = listening.url
  tokenRequests = []
})

afterAll(() => {
  provider.close()
})

/** Asks next-auth for the session the way GET /api/auth/session does. */
async function readSession(token: Parameters<typeof sessionCookie>[0]) {
  const cookie = await sessionCookie(token)
  return AuthHandler<Record<string, unknown>>({
    req: {
      action: 'session',
      method: 'GET',
      host: 'http://web.test/api/auth',
      headers: {},
      cookies: { 'next-auth.session-token': cookie.slice(cookie.indexOf('=') + 1) },
    },
    options: buildAuthOptions(readSettings({ ...ENV, OIDC_ISSUER: issuer })),
  })
}

function sessionTokenCookie(response: Awaited<ReturnType<typeof readSession>>) {
  return response.cookies!.find(cookie => cookie.name === 'next-auth.session-token')!
}

describe('session returned to the browser', () => {
  it('contains no access, refresh or ID token', async () => {
    const response = await readSession({
      sub: 'person-1',
      accessToken: 'access-token-value',
      refreshToken: 'refresh-token-value',
      idToken: 'id-token-value',
      expiresAt: now() + 3600,
    })

    expect(response.body).toEqual({ expires: expect.any(String) })
    expect(JSON.stringify(response.body)).not.toContain('token-value')
  })

  it('keeps the tokens in the encrypted cookie', async () => {
    const response = await readSession({
      sub: 'person-1',
      accessToken: 'access-token-value',
      refreshToken: 'refresh-token-value',
      idToken: 'id-token-value',
      expiresAt: now() + 3600,
    })

    const { value } = sessionTokenCookie(response)
    expect(value).not.toContain('token-value')
    expect(await decode({ token: value, secret: AUTH_SECRET })).toMatchObject({
      accessToken: 'access-token-value',
      refreshToken: 'refresh-token-value',
      idToken: 'id-token-value',
    })
  })
})

describe('access token about to expire', () => {
  it('is renewed with the refresh token, and the new one stays out of the session', async () => {
    const response = await readSession({
      sub: 'person-1',
      accessToken: 'access-token-value',
      refreshToken: 'refresh-token-value',
      idToken: 'id-token-value',
      expiresAt: now() + 30,
    })

    expect(tokenRequests).toHaveLength(1)
    expect(tokenRequests[0]!.body.get('grant_type')).toBe('refresh_token')
    expect(tokenRequests[0]!.body.get('refresh_token')).toBe('refresh-token-value')
    expect(tokenRequests[0]!.authorization).toBe(`Basic ${Buffer.from('zrs-web:client-secret').toString('base64')}`)

    expect(response.body).toEqual({ expires: expect.any(String) })
    const renewed = await decode({ token: sessionTokenCookie(response).value, secret: AUTH_SECRET })
    expect(renewed).toMatchObject({
      sub: 'person-1',
      accessToken: 'renewed-access-token-value',
      // The provider sent neither of these again, so the ones of the sign-in stay.
      refreshToken: 'refresh-token-value',
      idToken: 'id-token-value',
    })
    expect(renewed!.expiresAt).toBeGreaterThan(now() + 200)
  })

  it('ends the session when the provider refuses the refresh', async () => {
    refuseRefresh = true

    const response = await readSession({
      sub: 'person-1',
      accessToken: 'access-token-value',
      refreshToken: 'revoked-refresh-token-value',
      idToken: 'id-token-value',
      expiresAt: now() - 10,
    })

    expect(response.body).toEqual({})
    expect(sessionTokenCookie(response)).toMatchObject({ value: '', options: { maxAge: 0 } })
  })

  it('lasts until the access token expires when there is no refresh token', async () => {
    const response = await readSession({
      sub: 'person-1',
      accessToken: 'access-token-value',
      idToken: 'id-token-value',
      expiresAt: now() + 30,
    })

    expect(response.body).toEqual({ expires: expect.any(String) })
  })

  it('ends the session when the access token has expired and there is no refresh token', async () => {
    const response = await readSession({
      sub: 'person-1',
      accessToken: 'access-token-value',
      idToken: 'id-token-value',
      expiresAt: now() - 10,
    })

    expect(response.body).toEqual({})
    expect(sessionTokenCookie(response)).toMatchObject({ value: '', options: { maxAge: 0 } })
  })
})
