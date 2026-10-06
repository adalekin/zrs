import { defineEventHandler } from 'h3'
import { proxyToApi } from '../../utils/api-proxy'
import { readSessionToken } from '../../utils/session'
import { useSettings } from '../../utils/settings'

export default defineEventHandler(async (event) => {
  const token = await readSessionToken(event)
  return proxyToApi(event, useSettings().apiUrl, token?.accessToken)
})
