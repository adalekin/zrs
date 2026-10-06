import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  compatibilityDate: '2026-10-01',
  // The build tools report nothing to anybody.
  telemetry: false,
  app: {
    head: { title: 'ZRS', link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }] },
  },
  modules: ['shadcn-nuxt', '@nuxtjs/i18n', '@sidebase/nuxt-auth'],
  css: ['~/assets/css/tailwind.css', 'vue-sonner/style.css'],
  vite: {
    plugins: [tailwindcss()],
  },
  shadcn: {
    prefix: '',
    componentDir: '@/components/ui',
  },
  i18n: {
    // One interface language per installation: UI_LOCALE picks it at run time
    // (app/plugins/locale.ts), so there are no locale prefixes and no detection.
    strategy: 'no_prefix',
    detectBrowserLanguage: false,
    defaultLocale: 'en',
    locales: [
      { code: 'ru', language: 'ru', file: 'ru.json' },
      { code: 'en', language: 'en', file: 'en.json' },
    ],
  },
  auth: {
    // AUTH_ORIGIN holds the public address of the app. The module wants the address of
    // its own routes, so server/utils/settings.ts derives it into this variable.
    originEnvKey: 'ZRS_AUTH_BASE_URL',
    provider: {
      type: 'authjs',
      defaultProvider: 'oidc',
    },
    sessionRefresh: {
      // Each session read lets the server renew an access token that is about to expire.
      enablePeriodically: 60_000,
      enableOnWindowFocus: true,
    },
  },
  nitro: {
    // Listed here, not left to the directory scan, so that the settings are checked
    // before the plugins that modules add.
    plugins: ['~~/server/startup/settings.ts'],
  },
})
