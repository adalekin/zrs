// The payment day of the installation: the people who make the payments stop at a time of day
// on their own clock, and a deadline is judged against that clock, not the one of the reader.

// Imported by name: a unit test reads this file outside Nuxt, where the shared types are not global.
import type { PaymentDaySetting } from '../../shared/types/api'

/** Whether the payment of a request can be made by its deadline. */
export type DeadlineVerdict = 'in_time' | 'too_late_today' | 'passed'

/** A calendar day and a time of day on one clock, in the forms that compare as text. */
interface Clock {
  /** YYYY-MM-DD */
  day: string
  /** HH:MM */
  time: string
}

export class PaymentDay {
  private constructor(
    /** HH:MM on the clock of the installation. */
    private readonly endsAt: string,
    private readonly timezone: string,
  ) {}

  static of(setting: PaymentDaySetting): PaymentDay {
    return new PaymentDay(setting.ends_at, setting.timezone)
  }

  /** Whether a payment with this deadline, a calendar day, can still be made at this moment. */
  judge(deadline: string, moment: Date): DeadlineVerdict {
    const now = PaymentDay.clock(moment, this.timezone)
    if (deadline < now.day) {
      return 'passed'
    }
    return deadline === now.day && now.time >= this.endsAt ? 'too_late_today' : 'in_time'
  }

  /** The calendar day of a moment on the clock of the installation, as YYYY-MM-DD. */
  dayOf(moment: Date): string {
    return PaymentDay.clock(moment, this.timezone).day
  }

  /**
   * The end of the payment day as a reader in `zone` is told it: with the zone of the
   * installation named when the clock of the reader shows another time.
   */
  closing(moment: Date, zone: string, locale: string): string {
    const here = PaymentDay.clock(moment, zone)
    const there = PaymentDay.clock(moment, this.timezone)
    if (here.day === there.day && here.time === there.time) {
      return this.endsAt
    }
    const name = new Intl.DateTimeFormat(locale, { timeZone: this.timezone, timeZoneName: 'short' })
      .formatToParts(moment)
      .find(part => part.type === 'timeZoneName')!.value
    return `${this.endsAt} ${name}`
  }

  private static clock(moment: Date, zone: string): Clock {
    const parts = new Intl.DateTimeFormat('sv-SE', {
      timeZone: zone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(moment)
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(entry => entry.type === type)!.value
    return { day: `${part('year')}-${part('month')}-${part('day')}`, time: `${part('hour')}:${part('minute')}` }
  }
}
