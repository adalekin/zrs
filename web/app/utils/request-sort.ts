// The order of requests as the address of the page and the headings of the list speak of it.
// The server owns the orders themselves (server/internal/service/request_order.py).

// Imported by name: a unit test reads this file outside Nuxt, where the shared types are not global.
import type { RequestSort } from '../../shared/types/api'

/** A column of the list a person may sort by. */
export type SortColumn = 'priority' | 'deadline' | 'created'

/** The list opens as it always did: the newest request first. */
export const LIST_SORT: RequestSort = '-created'
/** A column of the board is the queue of one step: what is dealt with first stands on top. */
export const BOARD_SORT: RequestSort = 'priority'
/** The orders the board offers, one choice for all its columns. */
export const BOARD_SORTS: readonly RequestSort[] = ['priority', 'deadline', '-created']

/** The orders the list offers where it has no headings to click: every column, the first-click order before the turned one. */
export const LIST_SORTS: readonly RequestSort[] = ['-created', 'created', 'priority', '-priority', 'deadline', '-deadline']

/** What a first click on a column asks for: the highest priority, the nearest deadline, the newest request. */
const FIRST: Record<SortColumn, RequestSort> = { priority: 'priority', deadline: 'deadline', created: '-created' }

export const sortColumn = (sort: RequestSort) => (sort.startsWith('-') ? sort.slice(1) : sort) as SortColumn

/** The locale key of the name of an order: the turned order of a column has a name of its own. */
export function sortLabel(sort: RequestSort) {
  const column = sortColumn(sort)
  return sort === FIRST[column] ? `requests.sort.${column}` : `requests.sort.turned.${column}`
}

/** The order a click on the heading of a column leads to: a first click sorts by it, a second one turns the order over. */
export function nextSort(current: RequestSort, column: SortColumn): RequestSort {
  if (sortColumn(current) !== column) {
    return FIRST[column]
  }
  return current.startsWith('-') ? column : `-${column}`
}

/** How the heading of a column shows the order: not sorted by it, the first-click order, or the turned one. */
export function sortState(current: RequestSort, column: SortColumn): 'none' | 'first' | 'turned' {
  if (sortColumn(current) !== column) {
    return 'none'
  }
  return current === FIRST[column] ? 'first' : 'turned'
}
