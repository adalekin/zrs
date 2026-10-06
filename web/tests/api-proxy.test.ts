import type { IncomingHttpHeaders, Server } from 'node:http'
import { createApp, createRouter, toNodeListener } from 'h3'
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { chunkedSessionCookie, ENV, LARGE_TOKENS, listen, readBody, sessionCookie } from './helpers'

interface Received {
  method?: string
  url?: string
  headers: IncomingHttpHeaders
  body: Buffer
}

const PDF = Buffer.from([0x25, 0x50, 0x44, 0x46, 0x00, 0xFF, 0x10])

let api: Server
let web: Server
let webUrl: string
let received: Received[]
let cookie: string

beforeAll(async () => {
  // Stands in for the server: records what the proxy sent and answers like the API does.
  const upstream = await listen(async (req, res) => {
    received.push({ method: req.method, url: req.url, headers: req.headers, body: await readBody(req) })

    if (req.url === '/v1/me') {
      res.writeHead(403, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ detail: 'No role grants you access to this service' }))
    }
    else if (req.url === '/v1/requests/7/attachments/3') {
      res.writeHead(200, {
        'content-type': 'application/pdf',
        'content-disposition': 'attachment; filename*=UTF-8\'\'invoice.pdf',
      })
      res.end(PDF)
    }
    else {
      res.writeHead(201, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ id: 7 }))
    }
  })
  api = upstream.server

  for (const [name, value] of Object.entries({ ...ENV, API_URL: upstream.url })) {
    vi.stubEnv(name, value)
  }
  // Imported after the environment is set: the route reads the settings of the process.
  const { default: route } = await import('../server/api/v1/[...path]')
  const app = createApp().use(createRouter().use('/api/v1/**', route))
  const listening = await listen(toNodeListener(app))
  web = listening.server
  webUrl = listening.url

  cookie = await sessionCookie({
    sub: 'person-1',
    accessToken: 'access-token-value',
    refreshToken: 'refresh-token-value',
    idToken: 'id-token-value',
    expiresAt: Math.floor(Date.now() / 1000) + 300,
  })
})

beforeEach(() => {
  received = []
})

afterAll(() => {
  web.close()
  api.close()
  vi.unstubAllEnvs()
})

describe('/api/v1/** proxy route', () => {
  it('adds the access token of the session and forwards method, query, body and the answer', async () => {
    const response = await fetch(`${webUrl}/api/v1/requests?status=new&page=2`, {
      method: 'POST',
      headers: { 'cookie': cookie, 'content-type': 'application/json' },
      body: JSON.stringify({ amount: '1590.0000' }),
    })

    expect(response.status).toBe(201)
    expect(await response.json()).toEqual({ id: 7 })

    expect(received).toHaveLength(1)
    const [request] = received
    expect(request!.method).toBe('POST')
    expect(request!.url).toBe('/v1/requests?status=new&page=2')
    expect(request!.headers.authorization).toBe('Bearer access-token-value')
    expect(request!.headers['content-type']).toBe('application/json')
    expect(JSON.parse(request!.body.toString())).toEqual({ amount: '1590.0000' })
  })

  it('reads a session cookie that the browser holds in several chunks', async () => {
    const chunked = await chunkedSessionCookie({
      sub: 'person-1',
      ...LARGE_TOKENS,
      expiresAt: Math.floor(Date.now() / 1000) + 300,
    })
    expect(chunked).toContain('next-auth.session-token.0=')
    expect(chunked).toContain('next-auth.session-token.1=')

    const response = await fetch(`${webUrl}/api/v1/requests`, { headers: { cookie: chunked } })

    expect(response.status).toBe(201)
    expect(received[0]!.headers.authorization).toBe(`Bearer ${LARGE_TOKENS.accessToken}`)
  })

  it('keeps the session cookie to itself', async () => {
    await fetch(`${webUrl}/api/v1/requests`, { headers: { cookie } })

    expect(received[0]!.headers.cookie).toBeUndefined()
  })

  it('forwards an error status with its body', async () => {
    const response = await fetch(`${webUrl}/api/v1/me`, { headers: { cookie } })

    expect(response.status).toBe(403)
    expect(await response.json()).toEqual({ detail: 'No role grants you access to this service' })
  })

  it('passes a multipart upload through', async () => {
    const form = new FormData()
    form.append('file', new Blob([PDF], { type: 'application/pdf' }), 'invoice.pdf')

    const response = await fetch(`${webUrl}/api/v1/requests/7/attachments`, {
      method: 'POST',
      headers: { cookie },
      body: form,
    })

    expect(response.status).toBe(201)
    const [request] = received
    expect(request!.headers['content-type']).toMatch(/^multipart\/form-data; boundary=/)
    expect(request!.body.includes(PDF)).toBe(true)
    expect(request!.body.toString('latin1')).toContain('filename="invoice.pdf"')
  })

  it('passes a file download through with its content headers', async () => {
    const response = await fetch(`${webUrl}/api/v1/requests/7/attachments/3`, { headers: { cookie } })

    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toBe('application/pdf')
    expect(response.headers.get('content-disposition')).toBe('attachment; filename*=UTF-8\'\'invoice.pdf')
    expect(Buffer.from(await response.arrayBuffer()).equals(PDF)).toBe(true)
  })

  it('answers 401 without a session and does not call the server', async () => {
    const response = await fetch(`${webUrl}/api/v1/me`)

    expect(response.status).toBe(401)
    expect(await response.json()).toEqual({ detail: 'Not authenticated' })
    expect(received).toHaveLength(0)
  })

  it('does not reach outside /v1 of the server', async () => {
    const response = await fetch(`${webUrl}/api/v1/%2e%2e/health`, { headers: { cookie } })

    expect(response.status).toBe(404)
    expect(received).toHaveLength(0)
  })
})
