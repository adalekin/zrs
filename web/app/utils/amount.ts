// The amount field of the request form: what a person types against what the API takes.

function separators(locale: string) {
  const parts = new Intl.NumberFormat(locale).formatToParts(12345.6)
  return {
    group: parts.find(part => part.type === 'group')!.value,
    decimal: parts.find(part => part.type === 'decimal')!.value,
  }
}

/**
 * The typed amount as the API takes it: digits with a decimal point. Spaces between
 * digits are dropped, and so are the group separators of the language when they stand
 * where that language puts them. Anything else goes as typed for the server to refuse:
 * the form never guesses what a number meant.
 */
export function parseAmount(text: string, locale: string): string {
  const { group, decimal } = separators(locale)
  let value = text.replace(/\s/g, '')
  if (group.trim() !== '' && new RegExp(`^\\d{1,3}(\\${group}\\d{3})+(\\${decimal}\\d*)?$`).test(value)) {
    value = value.replaceAll(group, '')
  }
  return value.replace(decimal, '.')
}

/** 1500000 reads as 1 500 000: a missing or an extra zero is seen before the request is sent. */
export function groupAmount(text: string): string {
  const match = /^(\d+)([.,]\d*)?$/.exec(text.replace(/\s/g, ''))
  return match ? match[1]!.replace(/\B(?=(\d{3})+$)/g, '\u00A0') + (match[2] ?? '') : text
}

/** The amount of the API as a person would type it: no trailing zeros, the decimal separator of the language. */
export function typedAmount(value: string, locale: string): string {
  const trimmed = value.includes('.') ? value.replace(/\.?0+$/, '') : value
  return groupAmount(trimmed.replace('.', separators(locale).decimal))
}
