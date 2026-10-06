import { defineEventHandler } from 'h3'
import { orderSessionChunks } from '../utils/cookie-order'

// Runs before every other handler (the file name sorts first), so that next-auth and
// the routes of this app all read the session cookie the same way.
export default defineEventHandler((event) => {
  const { headers } = event.node.req
  if (headers.cookie) {
    headers.cookie = orderSessionChunks(headers.cookie)
  }
})
