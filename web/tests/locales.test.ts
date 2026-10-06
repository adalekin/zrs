import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import ru from '../i18n/locales/ru.json'

type Messages = { [key: string]: string | Messages }

function keys(messages: Messages, prefix = ''): string[] {
  return Object.entries(messages).flatMap(([key, value]) =>
    typeof value === 'string' ? [prefix + key] : keys(value, `${prefix}${key}.`),
  ).sort()
}

describe('locale files', () => {
  it('have exactly the same keys in ru and en', () => {
    expect(keys(ru)).toEqual(keys(en))
    expect(keys(ru).length).toBeGreaterThan(0)
  })

  it('use no long dash in the Russian copy', () => {
    expect(JSON.stringify(ru)).not.toContain('—')
  })
})
