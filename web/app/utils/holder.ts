// Who has the request now. Follows the transitions of the server
// (server/internal/service/transitions.py): each status that is not final waits for one party.

export type Holder = 'author' | 'moderator' | 'finance_director' | 'payer'

const HOLDERS: Partial<Record<Status, Holder>> = {
  returned: 'author',
  new: 'moderator',
  escalated: 'finance_director',
  approved: 'payer',
}

/** The party the request waits for; nobody once it is paid or rejected. */
export function holderOf(status: Status): Holder | undefined {
  return HOLDERS[status]
}

/** The parties in the order a request passes them. */
export const WAY: readonly Holder[] = ['author', 'moderator', 'finance_director', 'payer']

/** The statuses of a request on its way, in the order of the parties that hold it: the columns of the board. */
export const STATUSES_ON_THE_WAY: Status[] = (Object.entries(HOLDERS) as [Status, Holder][])
  .sort(([, one], [, other]) => WAY.indexOf(one) - WAY.indexOf(other))
  .map(([status]) => status)

/** The statuses a request does not leave. */
export const FINAL_STATUSES: Status[] = STATUSES.filter(status => HOLDERS[status] === undefined)
