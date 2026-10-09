import { describe, expect, it } from 'vitest'
import { RequestView, RequestViewMemory } from '../app/utils/request-view'

/** A storage in memory with the three methods the memory uses. */
function memory(): () => Storage {
  const items = new Map<string, string>()
  const storage = {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
    removeItem: (key: string) => void items.delete(key),
  } as Storage
  return () => storage
}

/** A browser that refuses the very access to the storage, as one with site data blocked does. */
function refusing(): Storage {
  throw new DOMException('The operation is insecure.', 'SecurityError')
}

/** A storage that is open and full. */
const full = () => ({
  getItem: () => null,
  setItem: () => {
    throw new DOMException('The quota has been exceeded.', 'QuotaExceededError')
  },
}) as unknown as Storage

const board = RequestView.named({ view: 'all', layout: 'board', sort: '-priority' })!

describe('RequestView.named', () => {
  it('takes the tab, the layout, the order and the status an address names', () => {
    expect(RequestView.named({ view: 'all', layout: 'board', sort: 'deadline' }))
      .toEqual({ tab: 'all', layout: 'board', sort: 'deadline' })
    expect(RequestView.named({ awaiting_me: 'true' })).toEqual({ tab: 'queue', layout: 'list' })
    expect(RequestView.named({ view: 'all', status: 'approved' }))
      .toEqual({ tab: 'all', layout: 'list', status: 'approved' })
  })

  it('takes a status for the tab of all requests, as the page does', () => {
    expect(RequestView.named({ status: 'paid' })).toEqual({ tab: 'all', layout: 'list', status: 'paid' })
  })

  it('leaves out a tab the address does not name: the page chose it, not the person', () => {
    expect(RequestView.named({ layout: 'board' })).toEqual({ layout: 'board' })
    expect(RequestView.named({ sort: 'priority' })).toEqual({ layout: 'list', sort: 'priority' })
  })

  it('finds no view in an address that names none', () => {
    expect(RequestView.named({})).toBeUndefined()
    expect(RequestView.named({ page: '3' })).toBeUndefined()
  })

  it('finds no view in an address that names only what the application does not know', () => {
    expect(RequestView.named({ sort: 'amount', status: 'archived', layout: 'calendar' })).toBeUndefined()
  })

  it('names the layout an address carries, whatever a narrow screen shows', () => {
    expect(RequestView.named({ view: 'all', layout: 'board', status: 'new' }))
      .toEqual({ tab: 'all', layout: 'board', status: 'new' })
  })
})

describe('RequestView.parse', () => {
  it('reads a view with every field', () => {
    expect(RequestView.parse('{"tab":"all","layout":"board","sort":"deadline","status":"approved"}'))
      .toEqual({ tab: 'all', layout: 'board', sort: 'deadline', status: 'approved' })
  })

  it('reads a view without an order and a status', () => {
    expect(RequestView.parse('{"tab":"queue","layout":"list"}')).toEqual({ tab: 'queue', layout: 'list' })
  })

  it('reads a view without a tab: the person chose the board and no tab', () => {
    expect(RequestView.parse('{"layout":"board"}')).toEqual({ layout: 'board' })
  })

  it('reads back what a view is stored as', () => {
    expect(RequestView.parse(board.serialize())).toEqual(board)
  })

  it('takes nothing stored for no view', () => {
    expect(RequestView.parse(null)).toBeUndefined()
  })

  it('takes a text that does not parse for no view', () => {
    expect(RequestView.parse('{"tab":')).toBeUndefined()
    expect(RequestView.parse('"board"')).toBeUndefined()
    expect(RequestView.parse('null')).toBeUndefined()
  })

  it('takes a text with an unknown value for no view, not for a part of one', () => {
    expect(RequestView.parse('{"tab":"mine","layout":"board"}')).toBeUndefined()
    expect(RequestView.parse('{"tab":"all","layout":"calendar"}')).toBeUndefined()
    expect(RequestView.parse('{"tab":"all","layout":"board","sort":"amount"}')).toBeUndefined()
    expect(RequestView.parse('{"tab":"all","layout":"board","status":"archived"}')).toBeUndefined()
    expect(RequestView.parse('{"tab":"all"}')).toBeUndefined()
  })

  it('takes a status filter on the queue for no view: the queue has none', () => {
    expect(RequestView.parse('{"tab":"queue","layout":"list","status":"new"}')).toBeUndefined()
  })

  it('takes a text that sets nothing for no view', () => {
    expect(RequestView.parse('{"layout":"list"}')).toBeUndefined()
  })
})

describe('RequestView.toQuery', () => {
  it('opens the queue as a list in its own order', () => {
    expect(RequestView.named({ awaiting_me: 'true' })!.toQuery())
      .toEqual({ awaiting_me: 'true', view: undefined, layout: undefined, sort: undefined, status: undefined })
  })

  it('opens all requests filtered by a status', () => {
    expect(RequestView.named({ view: 'all', status: 'approved' })!.toQuery())
      .toEqual({ awaiting_me: undefined, view: 'all', layout: undefined, sort: undefined, status: 'approved' })
  })

  it('opens the board in a chosen order', () => {
    expect(RequestView.named({ view: 'all', layout: 'board', sort: 'deadline' })!.toQuery())
      .toEqual({ awaiting_me: undefined, view: 'all', layout: 'board', sort: 'deadline', status: undefined })
  })

  it('names no tab for a view without one, so that the page chooses it', () => {
    expect(RequestView.named({ layout: 'board' })!.toQuery())
      .toEqual({ awaiting_me: undefined, view: undefined, layout: 'board', sort: undefined, status: undefined })
  })
})

describe('RequestViewMemory', () => {
  it('gives back the view a person left', () => {
    const storage = memory()
    new RequestViewMemory(storage, 7).keep(board)
    expect(new RequestViewMemory(storage, 7).recall()).toEqual(board)
  })

  it('keeps the views of two people in one browser apart', () => {
    const storage = memory()
    new RequestViewMemory(storage, 7).keep(board)
    expect(new RequestViewMemory(storage, 8).recall()).toBeUndefined()
  })

  it('gives back nothing once the person put the page back as it opens by itself', () => {
    const storage = memory()
    new RequestViewMemory(storage, 7).keep(board)
    new RequestViewMemory(storage, 7).forget()
    expect(new RequestViewMemory(storage, 7).recall()).toBeUndefined()
  })

  it('forgets the view of one person only', () => {
    const storage = memory()
    new RequestViewMemory(storage, 7).keep(board)
    new RequestViewMemory(storage, 8).forget()
    expect(new RequestViewMemory(storage, 7).recall()).toEqual(board)
  })

  it('remembers nothing in a browser that refuses the storage', () => {
    const refused = new RequestViewMemory(refusing, 7)
    expect(() => refused.keep(board)).not.toThrow()
    expect(() => refused.forget()).not.toThrow()
    expect(refused.recall()).toBeUndefined()
  })

  it('remembers nothing in a storage that is full', () => {
    expect(() => new RequestViewMemory(full, 7).keep(board)).not.toThrow()
  })
})
