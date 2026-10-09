import { describe, expect, it } from 'vitest'
import { RequestStage } from '../app/utils/request-stage'
import type { RejectedAs, Status } from '../shared/types/api'

const request = (status: Status, rejected_as: RejectedAs | null = null) => ({ status, rejected_as })

describe('RequestStage.of', () => {
  it('gives every status on the way its own stage', () => {
    expect(RequestStage.of(request('returned'))).toBe(RequestStage.RETURNED)
    expect(RequestStage.of(request('new'))).toBe(RequestStage.NEW)
    expect(RequestStage.of(request('escalated'))).toBe(RequestStage.ESCALATED)
    expect(RequestStage.of(request('approved'))).toBe(RequestStage.APPROVED)
    expect(RequestStage.of(request('paid'))).toBe(RequestStage.PAID)
  })

  it('sets a rejection by the finance director apart from the other two', () => {
    expect(RequestStage.of(request('rejected', 'finance_director'))).toBe(RequestStage.REJECTED_BY_FINANCE_DIRECTOR)
    expect(RequestStage.of(request('rejected', 'moderator'))).toBe(RequestStage.REJECTED)
    expect(RequestStage.of(request('rejected', 'author'))).toBe(RequestStage.REJECTED)
  })

  it('keeps the status of the request in the stage', () => {
    expect(RequestStage.of(request('rejected', 'finance_director')).status).toBe('rejected')
    expect(RequestStage.of(request('approved')).status).toBe('approved')
  })
})

describe('RequestStage.ofStatus', () => {
  it('is the stage of a request in that status', () => {
    for (const status of ['returned', 'new', 'escalated', 'approved', 'paid'] as const) {
      expect(RequestStage.ofStatus(status)).toBe(RequestStage.of(request(status)))
    }
  })

  it('takes a rejection without a request for the plain one', () => {
    expect(RequestStage.ofStatus('rejected')).toBe(RequestStage.REJECTED)
  })
})

describe('the paint of a stage', () => {
  const stages = [
    RequestStage.RETURNED, RequestStage.NEW, RequestStage.ESCALATED, RequestStage.APPROVED,
    RequestStage.PAID, RequestStage.REJECTED, RequestStage.REJECTED_BY_FINANCE_DIRECTOR,
  ]

  it('differs from stage to stage', () => {
    expect(new Set(stages.map(stage => stage.paint.row)).size).toBe(stages.length)
    expect(new Set(stages.map(stage => stage.paint.badge)).size).toBe(stages.length)
  })

  it('is quiet for the finished requests alone, and not for the one the finance director rejected', () => {
    expect(stages.filter(stage => stage.quiet)).toEqual([RequestStage.PAID, RequestStage.REJECTED])
  })
})
