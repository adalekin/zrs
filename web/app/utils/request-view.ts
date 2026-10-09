// What the page of requests remembers between visits: the tab, the layout, the order and the
// status filter as the person set them. The address of the page stays the one source of what
// is shown; a remembered view only fills an address that names none of the four.

// Imported by name: a unit test reads this file outside Nuxt, where the shared types are not global.
import type { RequestSort, Status } from '../../shared/types/api'
import { REQUEST_SORTS, STATUSES } from '../../shared/types/api'

type Tab = 'queue' | 'all'
type Layout = 'list' | 'board'

const TABS: readonly unknown[] = ['queue', 'all'] satisfies Tab[]
const LAYOUTS: readonly unknown[] = ['list', 'board'] satisfies Layout[]

/**
 * A view of the page of requests a person set: a value that knows how it is written in the address
 * of the page and in the storage. There is no view that sets nothing: the page as it opens by itself
 * is nothing to remember, so the ways to make a view give none for it.
 */
export class RequestView {
  /** Absent while the person has not chosen a tab: the page then opens the queue when it has requests. */
  readonly tab?: Tab
  /** The layout the address names, not the one a narrow screen shows instead. */
  readonly layout: Layout
  /** Absent when the address names no order: the layout then goes by its own. */
  readonly sort?: RequestSort
  /** Only with the tab of all requests: the queue has no status filter. */
  readonly status?: Status

  private constructor(tab: Tab | undefined, layout: Layout, sort: RequestSort | undefined, status: Status | undefined) {
    this.tab = tab
    this.layout = layout
    this.sort = sort
    this.status = status
  }

  private static of(tab: Tab | undefined, layout: Layout, sort: RequestSort | undefined, status: Status | undefined) {
    return tab || layout === 'board' || sort || status ? new RequestView(tab, layout, sort, status) : undefined
  }

  /**
   * The view an address names. Only what it names: a tab the page chose by itself, by the rule of
   * the queue or because the queue could not be counted, is not what the person left.
   */
  static named(query: Record<string, unknown>): RequestView | undefined {
    const status = STATUSES.find(value => value === query.status)
    const tab = query.awaiting_me === 'true' ? 'queue' : query.view === 'all' || status ? 'all' : undefined
    return RequestView.of(
      tab,
      query.layout === 'board' ? 'board' : 'list',
      REQUEST_SORTS.find(value => value === query.sort),
      tab === 'all' ? status : undefined,
    )
  }

  /**
   * Reads a stored view. A text that does not parse or carries a value the application does not
   * know is no view at all: half a view would open a screen the person never left.
   */
  static parse(text: string | null): RequestView | undefined {
    if (text === null) {
      return undefined
    }
    let value: unknown
    try {
      value = JSON.parse(text)
    }
    catch (error) {
      if (error instanceof SyntaxError) {
        return undefined
      }
      throw error
    }
    if (typeof value !== 'object' || value === null) {
      return undefined
    }
    const { tab, layout, sort, status } = value as Record<string, unknown>
    const known = (tab === undefined || TABS.includes(tab))
      && LAYOUTS.includes(layout)
      && (sort === undefined || (REQUEST_SORTS as readonly unknown[]).includes(sort))
      && (status === undefined || ((STATUSES as readonly unknown[]).includes(status) && tab === 'all'))
    return known ? RequestView.of(tab as Tab, layout as Layout, sort as RequestSort, status as Status) : undefined
  }

  /** The text the view is stored as. */
  serialize(): string {
    return JSON.stringify({ tab: this.tab, layout: this.layout, sort: this.sort, status: this.status })
  }

  /** The parameters of the address that open the view. A view without a tab names none, and the page chooses it. */
  toQuery(): Record<'awaiting_me' | 'view' | 'layout' | 'sort' | 'status', string | undefined> {
    return {
      awaiting_me: this.tab === 'queue' ? 'true' : undefined,
      view: this.tab === 'all' ? 'all' : undefined,
      layout: this.layout === 'board' ? 'board' : undefined,
      sort: this.sort,
      status: this.status,
    }
  }
}

/**
 * Keeps the view one person left on the page of requests in a storage of the browser. It does not
 * look into the view. A browser that refuses the storage remembers nothing, and the page works on.
 */
export class RequestViewMemory {
  private readonly open: () => Storage
  private readonly key: string

  /**
   * @param open Gives the storage. It is called inside the guard of every use: a browser may refuse
   *   the very access to its storage.
   */
  constructor(open: () => Storage, personId: number) {
    this.open = open
    this.key = `zrs:requests-view:${personId}`
  }

  /** The view the person left in this browser, if any. */
  recall(): RequestView | undefined {
    try {
      return RequestView.parse(this.open().getItem(this.key))
    }
    catch (error) {
      if (error instanceof DOMException) {
        return undefined
      }
      throw error
    }
  }

  keep(view: RequestView) {
    this.write(storage => storage.setItem(this.key, view.serialize()))
  }

  /** Remembers nothing from now on: the person put the page back as it opens by itself. */
  forget() {
    this.write(storage => storage.removeItem(this.key))
  }

  private write(change: (storage: Storage) => void) {
    try {
      change(this.open())
    }
    catch (error) {
      // See recall.
      if (!(error instanceof DOMException)) {
        throw error
      }
    }
  }
}
