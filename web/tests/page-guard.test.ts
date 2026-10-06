import type { Server } from 'node:http'
import { createApp, defineEventHandler, toNodeListener } from 'h3'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { chunkedSessionCookie, ENV, LARGE_TOKENS, listen, sessionCookie } from './helpers'

let web: Server
let webUrl: string

beforeAll(async () => {
  for (const [name, value] of Object.entries(ENV)) {
    vi.stubEnv(name, value)
  }
  const { default: sessionCookieOrder } = await import('../server/middleware/0.session-cookie-order')
  const { default: pageGuard } = await import('../server/middleware/page-guard')
  const app = createApp()
    .use(sessionCookieOrder)
    .use(pageGuard)
    .use(defineEventHandler(() => 'reached'))
  const listening = await listen(toNodeListener(app))
  web = listening.server
  webUrl = listening.url
})

afterAll(() => {
  web.close()
  vi.unstubAllEnvs()
})

function open(path: string, headers: Record<string, string> = {}) {
  return fetch(`${webUrl}${path}`, { redirect: 'manual', headers: { accept: 'text/html', ...headers } })
}

describe('page guard', () => {
  it('sends a visitor without a session to sign-in with a callback to the same page', async () => {
    const response = await open('/?status=new&awaiting_me=true')

    expect(response.status).toBe(302)
    const location = new URL(response.headers.get('location')!, webUrl)
    expect(location.pathname).toBe('/sign-in')
    expect([...location.searchParams.keys()]).toEqual(['callbackUrl'])
    expect(location.searchParams.get('callbackUrl')).toBe('/?status=new&awaiting_me=true')
  })

  it('lets a person with a session through', async () => {
    const cookie = await sessionCookie({
      sub: 'person-1',
      accessToken: 'access-token-value',
      idToken: 'id-token-value',
      expiresAt: Math.floor(Date.now() / 1000) + 300,
    })

    const response = await open('/requests/5', { cookie })

    expect(response.status).toBe(200)
    expect(await response.text()).toBe('reached')
  })

  it('lets a person through whose session cookie is split into chunks', async () => {
    const cookie = await chunkedSessionCookie({
      sub: 'person-1',
      ...LARGE_TOKENS,
      expiresAt: Math.floor(Date.now() / 1000) + 300,
    })

    const response = await open('/requests/5', { cookie })

    expect(response.status).toBe(200)
  })

  it('reads the chunks of the session cookie in whatever order the client lists them', async () => {
    const cookie = await chunkedSessionCookie({
      sub: 'person-1',
      ...LARGE_TOKENS,
      expiresAt: Math.floor(Date.now() / 1000) + 300,
    })
    const reversed = cookie.split('; ').reverse().join('; ')
    expect(reversed).toMatch(/^next-auth\.session-token\.2=/)

    const response = await open('/requests/5', { cookie: `other=1; ${reversed}` })

    expect(response.status).toBe(200)
  })

  it('does not accept a session cookie encrypted with another secret', async () => {
    const { encode } = await import('next-auth/jwt')
    const forged = await encode({ token: { sub: 'person-1' } as never, secret: 'another-secret' })

    const response = await open('/', { cookie: `next-auth.session-token=${forged}` })

    expect(response.status).toBe(302)
  })

  it.each(['/sign-in?callbackUrl=%2F', '/api/v1/me', '/api/auth/session', '/_nuxt/entry.js'])(
    'leaves %s to its own handler',
    async (path) => {
      const response = await open(path)

      expect(response.status).toBe(200)
    },
  )

  it('answers 401 to a request that is not a page navigation', async () => {
    const response = await open('/favicon.ico', { accept: 'image/*' })

    expect(response.status).toBe(401)
  })
})
