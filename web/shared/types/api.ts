// Shapes of the server API (server/internal/dto).

export const ROLES = ['requester', 'moderator', 'finance_director', 'payer'] as const
export type Role = (typeof ROLES)[number]

export const STATUSES = ['new', 'returned', 'escalated', 'approved', 'paid', 'rejected'] as const
export type Status = (typeof STATUSES)[number]

export type Action = 'approve' | 'escalate' | 'return' | 'reject' | 'resubmit' | 'cancel' | 'pay'

export const REFERENCE_KINDS = ['operation_type', 'payment_form', 'priority'] as const
export type ReferenceKind = (typeof REFERENCE_KINDS)[number]

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

export interface ExpenseRequestPage {
  items: ExpenseRequest[]
  total: number
  page: number
  size: number
}
