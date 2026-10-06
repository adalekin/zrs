// A chunk of the session cookie of next-auth: `<name>.<number>`.
const SESSION_CHUNK = /^(?:__Secure-)?next-auth\.session-token\.(\d+)$/

/**
 * Puts the chunks of a split session cookie into their numeric order.
 *
 * next-auth 4.21 joins the chunks in the order in which the Cookie header lists them.
 * Browsers list cookies by creation time (RFC 6265, section 5.4), which is the order of
 * the chunks; other clients need not, and a session read out of order cannot be
 * decrypted. The other cookies keep their places.
 */
export function orderSessionChunks(cookieHeader: string): string {
  const pairs = cookieHeader.split(/;\s*/)
  const positions: number[] = []
  const chunks: { pair: string, index: number }[] = []

  pairs.forEach((pair, position) => {
    const match = SESSION_CHUNK.exec(pair.slice(0, pair.indexOf('=')))
    if (match) {
      positions.push(position)
      chunks.push({ pair, index: Number(match[1]) })
    }
  })

  chunks.sort((a, b) => a.index - b.index)
  positions.forEach((position, order) => {
    pairs[position] = chunks[order]!.pair
  })
  return pairs.join('; ')
}
