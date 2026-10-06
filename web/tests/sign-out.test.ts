import type { Server } from 'node:http'
import { createApp, createRouter, toNodeListener } from 'h3'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { chunkedSessionCookie, ENV, LARGE_TOKENS, listen } from './helpers'

let provider: Server
let web: Server
let webUrl: string
let issuer: string

beforeAll(async () => {
  // Stands in for the identity provider: only its discovery document is needed.
  const providing = await listen((req, res) => {
    res.setHeader('content-type', 'application/json')
    res.end(JSON.stringify({ issuer, token_endpoint: `${issuer}/token`, end_session_endpoint: `${issuer}/logout` }))
  })
  provider = providing.server
  issuer = providing.url

  for (const [name, value] of Object.entries({ ...ENV, OIDC_ISSUER: issuer })) {
    vi.stubEnv(name, value)
  }
  const { default: signOut } = await import('../server/routes/sign-out.post')
  const listening = await listen(toNodeListener(createApp().use(createRouter().post('/sign-out', signOut))))
  web = listening.server
  webUrl = listening.url
})

afterAll(() => {
  web.close()
  provider.close()
  vi.unstubAllEnvs()
})

describe('sign-out', () => {
  it('removes every chunk of the session cookie and ends the session at the provider', async () => {
    const cookie = await chunkedSessionCookie({
      sub: 'person-1',
      ...LARGE_TOKENS,
      expiresAt: Math.floor(Date.now() / 1000) + 300,
    })
    const chunkNames = cookie.split('; ').map(pair => pair.slice(0, pair.indexOf('=')))
    expect(chunkNames.length).toBeGreaterThan(1)

    const response = await fetch(`${webUrl}/sign-out`, { method: 'POST', redirect: 'manual', headers: { cookie } })

    expect(response.status).toBe(303)
    const location = new URL(response.headers.get('location')!)
    expect(location.origin + location.pathname).toBe(`${issuer}/logout`)
    expect(location.searchParams.get('id_token_hint')).toBe(LARGE_TOKENS.idToken)
    expect(location.searchParams.get('client_id')).toBe('zrs-web')
    expect(location.searchParams.get('post_logout_redirect_uri')).toBe('http://web.test/')

    const removed = response.headers.getSetCookie()
    for (const name of chunkNames) {
      expect(removed).toContainEqual(expect.stringMatching(new RegExp(`^${name.replaceAll('.', '\\.')}=; Max-Age=0; Path=/`)))
    }
  })

  it('sends a visitor without a session back to the app and not to the provider', async () => {
    const response = await fetch(`${webUrl}/sign-out`, { method: 'POST', redirect: 'manual' })

    expect(response.status).toBe(303)
    expect(response.headers.get('location')).toBe('/')
  })
})
