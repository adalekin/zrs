import type { AuthOptions } from 'next-auth'
import { OidcError, refreshTokens } from './oidc'
import type { Settings } from './settings'

/** Id of the only sign-in provider; it is part of the redirect URI: /api/auth/callback/oidc. */
export const PROVIDER_ID = 'oidc'

/** With a refresh token, the access token is renewed this long before it expires. */
const REFRESH_MARGIN_SECONDS = 90

export function buildAuthOptions(settings: Settings): AuthOptions {
  return {
    secret: settings.authSecret,
    providers: [
      {
        id: PROVIDER_ID,
        name: 'OpenID Connect',
        type: 'oauth',
        wellKnown: `${settings.oidcIssuer}/.well-known/openid-configuration`,
        authorization: { params: { scope: 'openid profile email' } },
        idToken: true,
        checks: ['pkce', 'state'],
        clientId: settings.oidcClientId,
        clientSecret: settings.oidcClientSecret,
        // The name and the roles of the person come from the server (GET /v1/me),
        // so nothing but the subject is read from the ID token.
        profile: (claims: { sub: string }) => ({ id: claims.sub }),
      },
    ],
    callbacks: {
      async jwt({ token, account }) {
        if (account) {
          // Sign-in: keep the tokens of the provider in the session cookie.
          const { access_token, id_token, expires_at, refresh_token } = account
          if (!access_token || !id_token || !expires_at) {
            throw new OidcError('The token response has no access_token, id_token or expires_in')
          }
          return {
            sub: token.sub,
            accessToken: access_token,
            refreshToken: refresh_token,
            idToken: id_token,
            expiresAt: expires_at,
          }
        }

        // Without a refresh token there is nothing to renew: the session lasts as long
        // as the access token does.
        const renewAt = token.refreshToken ? token.expiresAt - REFRESH_MARGIN_SECONDS : token.expiresAt
        if (Date.now() / 1000 < renewAt) {
          return token
        }
        // An error here ends the session: next-auth removes the session cookie.
        return { sub: token.sub, ...(await refreshTokens(settings, token)) }
      },
      // The browser learns only that a session exists and when it expires.
      session: ({ session }) => ({ expires: session.expires }),
    },
  }
}
