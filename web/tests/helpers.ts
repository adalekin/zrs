import type { AddressInfo } from 'node:net'
import { createServer } from 'node:http'
import type { IncomingMessage, Server, ServerResponse } from 'node:http'
import { AuthHandler } from 'next-auth/core'
import { encode } from 'next-auth/jwt'
import type { JWT } from 'next-auth/jwt'

export const AUTH_SECRET = 'test-secret'

/** A complete environment; a test overrides or removes single variables. */
export const ENV = {
  OIDC_ISSUER: 'http://provider.test/realms/zrs',
  OIDC_CLIENT_ID: 'zrs-web',
  OIDC_CLIENT_SECRET: 'client-secret',
  AUTH_SECRET,
  AUTH_ORIGIN: 'http://web.test',
  API_URL: 'http://server.test:8000',
  UI_LOCALE: 'ru',
}

/** The Cookie header of a signed-in browser, encrypted the way next-auth does it. */
export async function sessionCookie(token: JWT): Promise<string> {
  return `next-auth.session-token=${await encode({ token, secret: AUTH_SECRET })}`
}

/** Tokens of a realistic size: together they do not fit into one cookie. */
export const LARGE_TOKENS = {
  accessToken: `access.${'a'.repeat(2000)}`,
  refreshToken: `refresh.${'r'.repeat(2000)}`,
  idToken: `id.${'i'.repeat(2000)}`,
}

/**
 * The Cookie header of a browser whose session does not fit into one cookie. next-auth
 * itself writes the cookies here, so they are split the way a browser receives them.
 */
export async function chunkedSessionCookie(token: JWT): Promise<string> {
  const { value } = (await sessionCookie(token)).match(/=(?<value>.*)$/)!.groups!
  const response = await AuthHandler({
    req: {
      action: 'session',
      method: 'GET',
      host: 'http://web.test/api/auth',
      headers: {},
      cookies: { 'next-auth.session-token': value },
    },
    options: { secret: AUTH_SECRET, providers: [] },
  })
  return response.cookies!
    // What a browser keeps: next-auth also sends the removal of the cookies it replaced.
    .filter(cookie => cookie.name.startsWith('next-auth.session-token') && cookie.value !== '')
    .map(cookie => `${cookie.name}=${cookie.value}`)
    .join('; ')
}

/** Starts an HTTP server on a free port and returns it with its address. */
export async function listen(
  handler: (req: IncomingMessage, res: ServerResponse) => void,
): Promise<{ server: Server, url: string }> {
  const server = createServer(handler)
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const { port } = server.address() as AddressInfo
  return { server, url: `http://127.0.0.1:${port}` }
}

export async function readBody(req: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = []
  for await (const chunk of req) {
    chunks.push(chunk as Buffer)
  }
  return Buffer.concat(chunks)
}
