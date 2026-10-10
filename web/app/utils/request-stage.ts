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
  /** The fill and the text of the status badge: deeper than the row it stands in. */
  badge: string
  /** The dot of a journal entry that brought the request to this stage. */
  dot: string
}

export class RequestStage {
  static readonly RETURNED = new RequestStage('returned', false, {
    row: 'bg-orange-50 hover:bg-orange-100/70',
    column: 'bg-orange-50',
    badge: 'bg-orange-200/70 text-orange-900',
    dot: 'bg-orange-500',
  })

  /** A new request has no colour: it is where every request starts. Its column and its badge are outlined instead. */
  static readonly NEW = new RequestStage('new', false, {
    row: 'hover:bg-muted/50',
    column: 'bg-background border',
    badge: 'bg-background text-foreground border',
    dot: 'bg-slate-400',
  })

  static readonly ESCALATED = new RequestStage('escalated', false, {
    row: 'bg-yellow-100/70 hover:bg-yellow-100',
    column: 'bg-yellow-100/70',
    badge: 'bg-yellow-300/60 text-yellow-950',
    dot: 'bg-yellow-500',
  })

  static readonly APPROVED = new RequestStage('approved', false, {
    row: 'bg-emerald-100/70 hover:bg-emerald-100',
    column: 'bg-emerald-100/70',
    badge: 'bg-emerald-300/50 text-emerald-950',
    dot: 'bg-emerald-500',
  })

  /** A paid request is done: its row is the palest, and its badge is the word with a tick, without a fill. */
  static readonly PAID = new RequestStage('paid', true, {
    row: 'bg-emerald-50/60 hover:bg-emerald-50',
    column: 'bg-emerald-50/60',
    badge: 'text-emerald-800',
    dot: 'bg-emerald-600',
  })

  /** Rejected by the moderator or cancelled by the author. */
  static readonly REJECTED = new RequestStage('rejected', true, {
    row: 'bg-neutral-200/60 hover:bg-neutral-200',
    column: 'bg-neutral-200/60',
    badge: 'bg-neutral-300/70 text-neutral-700',
    dot: 'bg-slate-400',
  })

  static readonly REJECTED_BY_FINANCE_DIRECTOR = new RequestStage('rejected', false, {
    row: 'bg-red-100/70 hover:bg-red-100',
    column: 'bg-red-100/70',
    badge: 'bg-red-300/50 text-red-950',
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
