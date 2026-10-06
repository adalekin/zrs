/**
 * Turns the field errors of a 422 answer into texts in the language of the interface.
 * An error the interface has no text for is shown as the server worded it.
 */
export function useFieldMessages() {
  const { t, te } = useI18n()

  return (error: unknown): Record<string, string> | undefined => {
    const byField = fieldErrors(error)
    if (!byField) {
      return undefined
    }
    return Object.fromEntries(
      Object.entries(byField).map(([field, { type, msg }]) => {
        const key = `error.field.${type}`
        return [field, type && te(key) ? t(key) : msg]
      }),
    )
  }
}
