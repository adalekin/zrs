/**
 * The Cookie header a browser would send after receiving `setCookies`: its own cookies,
 * with every cookie that was just set replacing the one of the same name.
 *
 * Replacing matters. A browser may still hold a CSRF cookie made with another secret
 * (after AUTH_SECRET was rotated, or from another app on the same host). next-auth then
 * issues a new one, and if the old one stayed first in the header the sign-in would be
 * refused as a CSRF mismatch.
 */
export function cookiesAfter(browserCookies: string | undefined, setCookies: string[]): string {
  const cookies = new Map<string, string>()
  const pairs = [...(browserCookies ? browserCookies.split(/;\s*/) : []), ...setCookies.map(cookie => cookie.split(';')[0]!)]
  for (const pair of pairs) {
    const separator = pair.indexOf('=')
    if (separator > 0) {
      cookies.set(pair.slice(0, separator), pair.slice(separator + 1))
    }
  }
  return [...cookies].map(([name, value]) => `${name}=${value}`).join('; ')
}
