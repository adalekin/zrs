// Shapes of the server API (server/internal/dto).

export const ROLES = ['requester', 'moderator', 'finance_director', 'payer'] as const
export type Role = (typeof ROLES)[number]

export const STATUSES = ['new', 'returned', 'escalated', 'approved', 'paid', 'rejected'] as const
export type Status = (typeof STATUSES)[number]

export type Action = 'approve' | 'escalate' | 'return' | 'reject' | 'resubmit' | 'cancel' | 'pay' | 'reassign' | 'finish'

/** How often a request is paid: once in every calendar period of this length. */
export const RECURRENCES = ['week', 'month', 'quarter', 'year'] as const
export type Recurrence = (typeof RECURRENCES)[number]

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

/** When the people who make the payments stop for the day. */
export interface PaymentDaySetting {
  /** HH:MM */
  ends_at: string
  /** The IANA time zone that time is in. */
  timezone: string
}

export interface Me extends Person {
  roles: Role[]
  currencies: string[]
  attachment_max_bytes: number
  payment_day: PaymentDaySetting
  notifications: {
    /** Whether the installation sends notifications. */
    enabled: boolean
    telegram_linked: boolean
  }
}

/** A one-time link that starts the bot of the installation for the current person. */
export interface TelegramLinkCode {
  url: string
  expires_at: string
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
  payer_changed: boolean
  /** The payer the entry gave the request; empty when it took the payer off or left them as they were. */
  payer: Person | null
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

/** What the person who rejected a request was to it: the author cancels, the other two reject. */
export type RejectedAs = 'author' | 'moderator' | 'finance_director'

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
  /** What the recurrence does not say about when to pay, in the words of the author. */
  payment_period: string | null
  /** Empty for a request paid once. */
  recurrence: Recurrence | null
  deadline: string | null
  /** The date of the latest payment. */
  paid_on: string | null
  /** The day a recurring request paid for this period comes back to its payer; empty while it waits for a payment. */
  next_payment_from: string | null
  /** Who rejected or cancelled the request. */
  rejected_by: Person | null
  rejected_as: RejectedAs | null
  created_at: string
  updated_at: string
}

export interface Payment {
  id: number
  person: Person
  paid_on: string
  /** Decimal number as a string, in the currency of the request. */
  amount: string
  created_at: string
}

export interface ExpenseRequestDetail extends ExpenseRequest {
  attachments: Attachment[]
  journal: JournalEntry[]
  /** The latest first. */
  payments: Payment[]
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
