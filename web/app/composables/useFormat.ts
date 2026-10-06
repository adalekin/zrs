/** Formats values in the interface language of the installation. */
export function useFormat() {
  const { locale } = useI18n()

  return {
    amount: (value: string, currency: string) =>
      // The amount stays a decimal string: Intl formats it without a float in between.
      new Intl.NumberFormat(locale.value, { style: 'currency', currency }).format(value as `${number}`),
    // A date without a time is a calendar day, the same in every time zone.
    date: (value: string) =>
      new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(value)),
    /** A day in a list: short, with the year only when it is not the current one. */
    day: (value: string) => {
      // A date without a time has ten characters; a moment is shown in the time zone of the browser.
      const timeZone = value.length === 10 ? 'UTC' : undefined
      const date = new Date(value)
      const year = date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric'
      return new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'short', year, timeZone }).format(date)
    },
    dateTime: (value: string) =>
      new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)),
    fileSize: (bytes: number) => {
      const megabyte = 1024 * 1024
      return bytes < megabyte
        ? new Intl.NumberFormat(locale.value, { style: 'unit', unit: 'kilobyte', maximumFractionDigits: 0 })
            .format(Math.ceil(bytes / 1024))
        : new Intl.NumberFormat(locale.value, { style: 'unit', unit: 'megabyte', maximumFractionDigits: 1 })
            .format(bytes / megabyte)
    },
  }
}
