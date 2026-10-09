// The stage of approval a request is at, and the colours the interface paints it in. A stage is
// the status of the request, except that a rejection by the finance director is a stage of its
// own: that request did not pass on money and may be returned to, the others are closed for good.
//
// Class names are written out in full: Tailwind collects them by reading the source.

// Imported by name: a unit test reads this file outside Nuxt, where the shared types are not global.
import type { ExpenseRequest, Status } from '../../shared/types/api'

interface Paint {
  /** The fill of a row of the list and of a card of the list, with the fill under the pointer. */
  row: string
  /** The fill of a column of the board. */
  column: string
  /** The fill and the text of the status badge: a stop deeper than the row it stands in. */
  badge: string
  /** The dot of a journal entry that brought the request to this stage. */
  dot: string
}

export class RequestStage {
  static readonly RETURNED = new RequestStage('returned', false, {
    row: 'bg-orange-100/60 hover:bg-orange-100',
    column: 'bg-orange-100/60',
    badge: 'bg-orange-200 text-orange-900',
    dot: 'bg-orange-500',
  })

  /** A new request has no colour: it is where every request starts. */
  static readonly NEW = new RequestStage('new', false, {
    row: 'hover:bg-muted/50',
    column: 'bg-muted/60',
    badge: 'bg-background text-foreground ring-border ring-1 ring-inset',
    dot: 'bg-slate-400',
  })

  static readonly ESCALATED = new RequestStage('escalated', false, {
    row: 'bg-yellow-100/60 hover:bg-yellow-100',
    column: 'bg-yellow-100/60',
    badge: 'bg-yellow-200 text-yellow-900',
    dot: 'bg-yellow-500',
  })

  static readonly APPROVED = new RequestStage('approved', false, {
    row: 'bg-green-100/60 hover:bg-green-100',
    column: 'bg-green-100/60',
    badge: 'bg-green-200 text-green-900',
    dot: 'bg-green-500',
  })

  static readonly PAID = new RequestStage('paid', true, {
    row: 'bg-green-50/70 hover:bg-green-50',
    column: 'bg-green-50/70',
    badge: 'bg-green-100 text-green-800',
    dot: 'bg-green-600',
  })

  /** Rejected by the moderator or cancelled by the author. */
  static readonly REJECTED = new RequestStage('rejected', true, {
    row: 'bg-muted/70 hover:bg-muted',
    column: 'bg-muted/70',
    badge: 'bg-foreground/10 text-muted-foreground',
    dot: 'bg-slate-400',
  })

  static readonly REJECTED_BY_FINANCE_DIRECTOR = new RequestStage('rejected', false, {
    row: 'bg-red-100/60 hover:bg-red-100',
    column: 'bg-red-100/60',
    badge: 'bg-red-200 text-red-900',
    dot: 'bg-red-500',
  })

  private static readonly BY_STATUS: Record<Status, RequestStage> = {
    returned: RequestStage.RETURNED,
    new: RequestStage.NEW,
    escalated: RequestStage.ESCALATED,
    approved: RequestStage.APPROVED,
    paid: RequestStage.PAID,
    rejected: RequestStage.REJECTED,
  }

  private constructor(
    readonly status: Status,
    /** The request is finished: its text is quiet. */
    readonly quiet: boolean,
    readonly paint: Paint,
  ) {}

  /** The stage of a request. */
  static of(request: Pick<ExpenseRequest, 'status' | 'rejected_as'>): RequestStage {
    return request.status === 'rejected' && request.rejected_as === 'finance_director'
      ? RequestStage.REJECTED_BY_FINANCE_DIRECTOR
      : RequestStage.BY_STATUS[request.status]
  }

  /** The stage a status stands for where there is no request to ask: a column, a total, a journal entry. */
  static ofStatus(status: Status): RequestStage {
    return RequestStage.BY_STATUS[status]
  }
}
