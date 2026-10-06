import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: {
    alias: {
      // The virtual module of @sidebase/nuxt-auth exists only inside a Nuxt build.
      '#auth': fileURLToPath(new URL('./tests/stubs/auth.ts', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
})
