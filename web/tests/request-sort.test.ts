import { describe, expect, it } from 'vitest'
import { nextSort, sortColumn, sortLabel, sortState } from '../app/utils/request-sort'

describe('nextSort', () => {
  it('puts on top what is dealt with first on a first click', () => {
    expect(nextSort('-created', 'priority')).toBe('priority')
    expect(nextSort('-created', 'deadline')).toBe('deadline')
    expect(nextSort('priority', 'created')).toBe('-created')
  })

  it('turns the order over on a second click', () => {
    expect(nextSort('priority', 'priority')).toBe('-priority')
    expect(nextSort('-priority', 'priority')).toBe('priority')
    expect(nextSort('deadline', 'deadline')).toBe('-deadline')
    expect(nextSort('-created', 'created')).toBe('created')
    expect(nextSort('created', 'created')).toBe('-created')
  })

  it('starts another column from its first order, whichever way the previous one went', () => {
    expect(nextSort('-priority', 'deadline')).toBe('deadline')
    expect(nextSort('-deadline', 'created')).toBe('-created')
  })
})

describe('sortColumn', () => {
  it('names the column of an order in either direction', () => {
    expect(sortColumn('-deadline')).toBe('deadline')
    expect(sortColumn('created')).toBe('created')
  })
})

describe('sortLabel', () => {
  it('names the first order of a column and the turned one differently', () => {
    expect(sortLabel('-created')).toBe('requests.sort.created')
    expect(sortLabel('created')).toBe('requests.sort.turned.created')
    expect(sortLabel('priority')).toBe('requests.sort.priority')
    expect(sortLabel('-deadline')).toBe('requests.sort.turned.deadline')
  })
})

describe('sortState', () => {
  it('tells the first order of a column from the turned one', () => {
    expect(sortState('-created', 'created')).toBe('first')
    expect(sortState('created', 'created')).toBe('turned')
    expect(sortState('priority', 'priority')).toBe('first')
    expect(sortState('-priority', 'priority')).toBe('turned')
  })

  it('says nothing about a column the list is not sorted by', () => {
    expect(sortState('priority', 'deadline')).toBe('none')
  })
})
