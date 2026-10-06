import { describe, expect, it } from 'vitest'
import { orderSessionChunks } from '../server/utils/cookie-order'

describe('order of session cookie chunks', () => {
  it('sorts the chunks by number and leaves the other cookies where they were', () => {
    const header = [
      'next-auth.session-token.10=k',
      'theme=dark',
      'next-auth.session-token.2=c',
      'next-auth.session-token.0=a',
      'next-auth.csrf-token=x%7Cy',
      'next-auth.session-token.1=b',
    ].join('; ')

    expect(orderSessionChunks(header)).toBe([
      'next-auth.session-token.0=a',
      'theme=dark',
      'next-auth.session-token.1=b',
      'next-auth.session-token.2=c',
      'next-auth.csrf-token=x%7Cy',
      'next-auth.session-token.10=k',
    ].join('; '))
  })

  it('orders the chunks of a session cookie sent over https', () => {
    expect(orderSessionChunks('__Secure-next-auth.session-token.1=b; __Secure-next-auth.session-token.0=a'))
      .toBe('__Secure-next-auth.session-token.0=a; __Secure-next-auth.session-token.1=b')
  })

  it('leaves a header without chunks unchanged', () => {
    expect(orderSessionChunks('next-auth.session-token=abc; theme=dark')).toBe('next-auth.session-token=abc; theme=dark')
  })
})
