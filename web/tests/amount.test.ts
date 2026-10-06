import { describe, expect, it } from 'vitest'
import { groupAmount, parseAmount, typedAmount } from '../app/utils/amount'

describe('parseAmount', () => {
  it('reads a Russian amount with spaces and a decimal comma', () => {
    expect(parseAmount('1\u00A0500 000,5', 'ru')).toBe('1500000.5')
  })

  it('takes a decimal point in the Russian interface', () => {
    expect(parseAmount('1500.5', 'ru')).toBe('1500.5')
  })

  it('reads a comma in the Russian interface as the decimal separator', () => {
    expect(parseAmount('1,500', 'ru')).toBe('1.500')
  })

  it('drops the group commas of an English amount', () => {
    expect(parseAmount('1,500', 'en')).toBe('1500')
    expect(parseAmount('1,500,000.25', 'en')).toBe('1500000.25')
  })

  it('reads an English amount grouped with spaces', () => {
    expect(parseAmount('1\u00A0500.5', 'en')).toBe('1500.5')
  })

  it('leaves a comma that is no group separator for the server to refuse', () => {
    expect(parseAmount('1500,5', 'en')).toBe('1500,5')
  })

  it('keeps an empty field empty', () => {
    expect(parseAmount(' ', 'ru')).toBe('')
  })
})

describe('groupAmount', () => {
  it('groups the digits before the decimal separator', () => {
    expect(groupAmount('1500000')).toBe('1\u00A0500\u00A0000')
    expect(groupAmount('1500000,5')).toBe('1\u00A0500\u00A0000,5')
    expect(groupAmount('1\u00A0500 000.25')).toBe('1\u00A0500\u00A0000.25')
  })

  it('leaves short amounts and text that is not a number as typed', () => {
    expect(groupAmount('999')).toBe('999')
    expect(groupAmount('1,500.5')).toBe('1,500.5')
    expect(groupAmount('about 5')).toBe('about 5')
  })
})

describe('typedAmount', () => {
  it('drops trailing zeros and uses the decimal separator of the language', () => {
    expect(typedAmount('1500000.5000', 'ru')).toBe('1\u00A0500\u00A0000,5')
    expect(typedAmount('1590.0000', 'en')).toBe('1\u00A0590')
    expect(typedAmount('0.2500', 'en')).toBe('0.25')
  })

  it('keeps the zeros of a whole amount', () => {
    expect(typedAmount('100', 'ru')).toBe('100')
  })
})
