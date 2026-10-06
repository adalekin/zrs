import { describe, expect, it } from 'vitest'
import { cookiesAfter } from '../server/utils/cookies'

describe('cookiesAfter', () => {
  it('keeps the cookies of the browser and adds the new ones', () => {
    expect(cookiesAfter('theme=dark', ['next-auth.csrf-token=new; Path=/; HttpOnly'])).toBe(
      'theme=dark; next-auth.csrf-token=new',
    )
  })

  it('replaces a stale cookie of the same name instead of sending both', () => {
    const header = cookiesAfter('next-auth.csrf-token=stale; theme=dark', [
      'next-auth.csrf-token=fresh%7Chash; Path=/; HttpOnly; SameSite=Lax',
    ])

    expect(header).toBe('next-auth.csrf-token=fresh%7Chash; theme=dark')
  })

  it('works when the browser sent no cookies', () => {
    expect(cookiesAfter(undefined, ['a=1; Path=/', 'b=2'])).toBe('a=1; b=2')
  })

  it('keeps "=" inside a cookie value', () => {
    expect(cookiesAfter('token=abc==', [])).toBe('token=abc==')
  })
})
