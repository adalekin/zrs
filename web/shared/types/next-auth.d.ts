import type { TokenSet } from '../../server/utils/oidc'

// Lives in shared/ because both the server project and the app project (through the
// typed routes) compile the server files that read the session.
declare module 'next-auth/jwt' {
  /** Content of the encrypted session cookie. */
  interface JWT extends TokenSet {
    sub?: string
  }
}
