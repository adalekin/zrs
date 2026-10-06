// Reading the error answers of the server API (server/internal/exceptions.py).

interface ApiFailure {
  statusCode?: number
  data?: {
    code?: string
    detail?: string | { type?: string, loc: (string | number)[], msg: string }[]
    status?: Status
    limit?: number
  }
}

function failure(error: unknown): ApiFailure {
  return typeof error === 'object' && error !== null ? error as ApiFailure : {}
}

export function apiStatus(error: unknown): number | undefined {
  return failure(error).statusCode
}

export interface FieldError {
  /** Stable code of the rule that failed; the interface has a text for the known ones. */
  type?: string
  /** English text from the server, shown when the interface has none of its own. */
  msg: string
}

/** Errors of a 422 answer by field: the field is the last item of `loc`. */
export function fieldErrors(error: unknown): Record<string, FieldError> | undefined {
  const { statusCode, data } = failure(error)
  if (statusCode !== 422 || !Array.isArray(data?.detail)) {
    return undefined
  }
  return Object.fromEntries(data.detail.map(({ type, loc, msg }) => [String(loc.at(-1)), { type, msg }]))
}

/** Stable code of an error answer (the class of the error on the server). */
export function errorCode(error: unknown): string | undefined {
  return failure(error).data?.code
}

/** The current status of the request from a 409 answer to an action that no longer fits it. */
export function conflictStatus(error: unknown): Status | undefined {
  const { statusCode, data } = failure(error)
  return statusCode === 409 && data?.code === 'StatusConflict' ? data.status : undefined
}

/** The size limit from a 413 answer to an upload. */
export function attachmentLimit(error: unknown): number | undefined {
  const { statusCode, data } = failure(error)
  return statusCode === 413 ? data?.limit : undefined
}

/** The message of the server, when the answer carries one. */
export function errorDetail(error: unknown): string | undefined {
  const { data } = failure(error)
  return typeof data?.detail === 'string' ? data.detail : undefined
}
