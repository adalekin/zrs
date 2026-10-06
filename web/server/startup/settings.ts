import { SettingsError, useSettings } from '../utils/settings'

declare module 'h3' {
  interface H3EventContext {
    uiLocale: 'ru' | 'en'
  }
}

export default defineNitroPlugin((nitroApp) => {
  let settings
  try {
    settings = useSettings()
  }
  catch (error) {
    if (!(error instanceof SettingsError)) {
      throw error
    }
    console.error(`[zrs-web] Cannot start: ${error.message}`)
    process.exit(1)
  }

  // The auth module reads the address of its own routes from the variable named in
  // `auth.originEnvKey` (nuxt.config.ts).
  process.env.ZRS_AUTH_BASE_URL = `${settings.authOrigin}/api/auth`

  const { uiLocale } = settings
  nitroApp.hooks.hook('request', (event) => {
    event.context.uiLocale = uiLocale
  })
})
