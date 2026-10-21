import { describe, expect, it } from 'vitest'
import { attachmentLimit } from '../app/utils/api-error'

describe('attachmentLimit', () => {
  it('reads the limit from the answer to a document over it', () => {
    const error = { statusCode: 413, data: { code: 'AttachmentTooLarge', limit: 10485760 } }
    expect(attachmentLimit(error)).toBe(10485760)
  })

  it('finds no limit in another error', () => {
    expect(attachmentLimit({ statusCode: 422, data: { code: 'ValidationError', detail: [] } })).toBeUndefined()
    expect(attachmentLimit({ statusCode: 413, data: { code: 'PayloadTooLarge' } })).toBeUndefined()
    expect(attachmentLimit(new Error('network'))).toBeUndefined()
  })
})
