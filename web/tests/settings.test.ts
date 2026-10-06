import { describe, expect, it } from 'vitest'
import { readSettings, SettingsError } from '../server/utils/settings'
import { ENV } from './helpers'

describe('settings of the installation', () => {
  it('reads a complete environment', () => {
    expect(readSettings({ ...ENV, API_URL: 'http://server.test:8000/' })).toEqual({
      oidcIssuer: 'http://provider.test/realms/zrs',
      oidcClientId: 'zrs-web',
      oidcClientSecret: 'client-secret',
      authSecret: 'test-secret',
      authOrigin: 'http://web.test',
      apiUrl: 'http://server.test:8000',
      uiLocale: 'ru',
    })
  })

  it.each(Object.keys(ENV))('stops when %s is missing and names it', (name) => {
    const read = () => readSettings({ ...ENV, [name]: undefined })

    expect(read).toThrow(SettingsError)
    expect(read).toThrow(`${name} is not set`)
  })

  it('stops on UI_LOCALE=de and names the variable', () => {
    const read = () => readSettings({ ...ENV, UI_LOCALE: 'de' })

    expect(read).toThrow(SettingsError)
    expect(read).toThrow('UI_LOCALE must be "ru" or "en", got "de"')
  })

  it('stops on AUTH_ORIGIN with a path and names the variable', () => {
    expect(() => readSettings({ ...ENV, AUTH_ORIGIN: 'http://web.test/api/auth' })).toThrow(/^AUTH_ORIGIN /)
  })

  it('stops on OIDC_ISSUER that is not a URL and names the variable', () => {
    expect(() => readSettings({ ...ENV, OIDC_ISSUER: 'provider.test' })).toThrow(/^OIDC_ISSUER /)
  })
})
