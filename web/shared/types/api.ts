// Shapes of the server API (server/internal/dto).

export const ROLES = ['requester', 'moderator', 'finance_director', 'payer'] as const
export type Role = (typeof ROLES)[number]

export const STATUSES = ['new', 'returned', 'escalated', 'approved', 'paid', 'rejected'] as const
export type Status = (typeof STATUSES)[number]

export type Action = 'approve' | 'escalate' | 'return' | 'reject' | 'resubmit' | 'cancel' | 'pay'

export const REFERENCE_KINDS = ['operation_type', 'payment_form', 'priority'] as const
export type ReferenceKind = (typeof REFERENCE_KINDS)[number]

export const REFERENCE_COLORS = ['red', 'orange', 'yellow', 'green', 'teal', 'blue', 'violet', 'pink'] as const
export type ReferenceColor = (typeof REFERENCE_COLORS)[number]

/** The orders of a list of requests; a minus turns the order over. */
export const REQUEST_SORTS = ['created', '-created', 'priority', '-priority', 'deadline', '-deadline'] as const
export type RequestSort = (typeof REQUEST_SORTS)[number]

export interface Person {
  id: number
  name: string
  email: string | null
}

export interface Me extends Person {
  roles: Role[]
  currencies: string[]
  attachment_max_bytes: number
}

export interface ReferenceItem {
  id: number
  kind: ReferenceKind
  name: string
  is_active: boolean
  /** The colour the finance director gave the value; null when it has none. */
  color: ReferenceColor | null
  /** The place of a priority in its list, from 1; null in the lists without an order. */
  position: number | null
}

export interface JournalEntry {
  id: number
  person: Person
  status: Status
  status_changed: boolean
  comment: string | null
  created_at: string
}

export interface Attachment {
  id: number
  filename: string
  content_type: string
  size: number
  created_at: string
}

export interface ExpenseRequest {
  id: number
  status: Status
  author: Person
  moderator: Person
  payer: Person | null
  operation_type: ReferenceItem
  payment_form: ReferenceItem | null
  priority: ReferenceItem
  situation: string
  solution: string
  /** Decimal number as a string, for example "1590.0000". */
  amount: string
  currency: string
  payment_period: string
  deadline: string | null
  paid_on: string | null
  created_at: string
  updated_at: string
}

export interface ExpenseRequestDetail extends ExpenseRequest {
  attachments: Attachment[]
  journal: JournalEntry[]
  /** Actions the current person may apply right now. */
  actions: Action[]
  /** Whether the current person may change fields and attachments right now. */
  can_edit: boolean
}

/** How many requests of one status a person sees and how much they add up to, per currency. */
export interface RequestTotals {
  status: Status
  count: number
  /** Decimal numbers as strings, like the amount of a request. */
  amounts: { currency: string, amount: string }[]
}

export interface ExpenseRequestPage {
  items: ExpenseRequest[]
  total: number
  page: number
  size: number
}
