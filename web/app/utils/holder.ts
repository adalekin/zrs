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
