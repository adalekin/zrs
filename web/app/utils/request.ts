// What a list and a board say about one request.

/** The first line of the situation: what the request is about. */
export const gist = (request: ExpenseRequest) => request.situation.split('\n', 1)[0]

/** The calendar day of the browser, in the form the API writes dates. */
export const calendarDay = () => new Date().toLocaleDateString('sv')

/** A deadline that has passed while the request is still on its way. `today` is a calendar day. */
export function isOverdue(request: ExpenseRequest, today: string) {
  return request.deadline !== null && holderOf(request.status) !== undefined && request.deadline < today
}

/** The reference values of a request in the order a card shows them; a request may have no payment form. */
export const marks = (request: ExpenseRequest) =>
  [request.operation_type, request.priority, request.payment_form].filter(item => item !== null)
