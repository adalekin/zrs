export const UI_LOCALES = ['ru', 'en'] as const
export type UiLocale = (typeof UI_LOCALES)[number]

export interface Settings {
  oidcIssuer: string
  oidcClientId: string
  oidcClientSecret: string
  authSecret: string
  /** Public origin of the web app, without a trailing slash. */
  authOrigin: string
  /** Base address of the server, without a trailing slash. */
  apiUrl: string
  uiLocale: UiLocale
}

/** A required setting is missing or invalid. The message names the variable. */
export class SettingsError extends Error {}

type Env = Record<string, string | undefined>

function required(env: Env, name: string): string {
  const value = env[name]
  if (value === undefined || value.trim() === '') {
    throw new SettingsError(`${name} is not set`)
  }
  return value.trim()
}

function httpUrl(env: Env, name: string): URL {
  const value = required(env, name)
  if (!URL.canParse(value)) {
    throw new SettingsError(`${name} must be an http(s) URL, got "${value}"`)
  }
  const url = new URL(value)
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new SettingsError(`${name} must be an http(s) URL, got "${value}"`)
  }
  return url
}

function withoutTrailingSlash(url: URL): string {
  return url.href.replace(/\/+$/, '')
}

/** Reads the settings of the installation. Nothing has a default value. */
export function readSettings(env: Env): Settings {
  const oidcIssuer = withoutTrailingSlash(httpUrl(env, 'OIDC_ISSUER'))
  const oidcClientId = required(env, 'OIDC_CLIENT_ID')
  const oidcClientSecret = required(env, 'OIDC_CLIENT_SECRET')
  const authSecret = required(env, 'AUTH_SECRET')

  const authOrigin = httpUrl(env, 'AUTH_ORIGIN')
  if (authOrigin.pathname !== '/' || authOrigin.search !== '' || authOrigin.hash !== '') {
    throw new SettingsError(
      `AUTH_ORIGIN must be the address of the web app without a path, got "${env.AUTH_ORIGIN}"`,
    )
  }

  const apiUrl = withoutTrailingSlash(httpUrl(env, 'API_URL'))

  const uiLocale = required(env, 'UI_LOCALE')
  if (!UI_LOCALES.includes(uiLocale as UiLocale)) {
    throw new SettingsError(`UI_LOCALE must be "ru" or "en", got "${uiLocale}"`)
  }

  return {
    oidcIssuer,
    oidcClientId,
    oidcClientSecret,
    authSecret,
    authOrigin: authOrigin.origin,
    apiUrl,
    uiLocale: uiLocale as UiLocale,
  }
}

let settings: Settings | undefined

/**
 * Settings of the running process. They are read from the environment when the server
 * starts, not at build time: one image serves every installation.
 */
export function useSettings(): Settings {
  settings ??= readSettings(process.env)
  return settings
}
