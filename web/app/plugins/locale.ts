/**
 * Sets the interface language of the installation (UI_LOCALE). The server puts it on
 * the request (server/startup/settings.ts); the browser gets it with the page state.
 */
export default defineNuxtPlugin({
  name: 'zrs:locale',
  dependsOn: ['i18n:plugin:route-locale-detect'],
  async setup(nuxtApp) {
    const locale = useState('ui-locale', () => useRequestEvent()!.context.uiLocale)

    await nuxtApp.$i18n.setLocale(locale.value)
    useHead({ htmlAttrs: { lang: locale.value } })
  },
})
