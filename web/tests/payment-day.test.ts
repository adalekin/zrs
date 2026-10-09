import { describe, expect, it } from 'vitest'
import { PaymentDay } from '../app/utils/payment-day'

// Moscow is three hours ahead of UTC the whole year.
const moscow = PaymentDay.of({ ends_at: '16:30', timezone: 'Europe/Moscow' })
const at = (utc: string) => new Date(`${utc}Z`)

describe('PaymentDay.judge', () => {
  it('lets a deadline of today pass before the payment day ends', () => {
    expect(moscow.judge('2026-10-09', at('2026-10-09T08:00:00'))).toBe('in_time')
    expect(moscow.judge('2026-10-09', at('2026-10-09T13:29:59'))).toBe('in_time')
  })

  it('finds a deadline of today too late from the minute the payment day ends', () => {
    expect(moscow.judge('2026-10-09', at('2026-10-09T13:30:00'))).toBe('too_late_today')
    expect(moscow.judge('2026-10-09', at('2026-10-09T14:10:00'))).toBe('too_late_today')
  })

  it('finds a deadline before today passed, whatever the time', () => {
    expect(moscow.judge('2026-10-08', at('2026-10-09T05:00:00'))).toBe('passed')
    expect(moscow.judge('2026-10-08', at('2026-10-09T14:10:00'))).toBe('passed')
  })

  it('lets a deadline of tomorrow pass after the payment day ended', () => {
    expect(moscow.judge('2026-10-10', at('2026-10-09T14:10:00'))).toBe('in_time')
  })

  it('takes the day of the installation, not of the moment in UTC', () => {
    // Half past midnight of the tenth in Moscow is still the ninth in UTC.
    const moment = at('2026-10-09T21:30:00')

    expect(moscow.judge('2026-10-09', moment)).toBe('passed')
    expect(moscow.judge('2026-10-10', moment)).toBe('in_time')
  })

  it('warns in the last minute alone when payments are made till the end of the day', () => {
    const tillMidnight = PaymentDay.of({ ends_at: '23:59', timezone: 'Europe/Moscow' })

    expect(tillMidnight.judge('2026-10-09', at('2026-10-09T20:58:59'))).toBe('in_time')
    expect(tillMidnight.judge('2026-10-09', at('2026-10-09T20:59:00'))).toBe('too_late_today')
  })
})

describe('PaymentDay.closing', () => {
  const moment = at('2026-10-09T14:00:00')

  it('is the bare time for a reader whose clock shows the time of the installation', () => {
    expect(moscow.closing(moment, 'Europe/Moscow', 'en')).toBe('16:30')
    expect(moscow.closing(moment, 'Europe/Minsk', 'en')).toBe('16:30')
  })

  it('names the zone of the installation for a reader on another clock', () => {
    expect(moscow.closing(moment, 'Asia/Yekaterinburg', 'en')).toMatch(/^16:30 \S+/)
    expect(moscow.closing(moment, 'Europe/Berlin', 'en')).toMatch(/^16:30 \S+/)
  })
})
