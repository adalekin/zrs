<script setup lang="ts">
import { BellIcon } from '@lucide/vue'

const api = useApi()
const me = useMe()

// 'forbidden': the person has signed in but holds none of the four roles.
const problem = ref<'forbidden' | 'unavailable'>()

onMounted(async () => {
  try {
    me.value = await api<Me>('/me')
  }
  catch (error) {
    problem.value = apiStatus(error) === 403 ? 'forbidden' : 'unavailable'
  }
})
</script>

<template>
  <main v-if="problem" class="mx-auto flex min-h-screen max-w-md flex-col items-start justify-center gap-4 p-6">
    <AppLogo />
    <h1 class="text-xl font-semibold">
      {{ problem === 'forbidden' ? $t('access.title') : 'ZRS' }}
    </h1>
    <p class="text-muted-foreground">
      {{ problem === 'forbidden' ? $t('access.noRole') : $t('common.unavailable') }}
    </p>
    <SignOutButton variant="outline" />
  </main>

  <div v-else-if="me" class="min-h-screen">
    <header class="border-b">
      <!-- The narrowest phones get smaller gaps: with two sections in the navigation the bar would not fit one line. -->
      <div class="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 max-[359px]:gap-x-3">
        <NuxtLink to="/" class="flex items-center gap-2 text-lg font-semibold">
          <AppLogo />
          ZRS
        </NuxtLink>
        <nav class="flex gap-4 text-sm max-[359px]:gap-3">
          <NuxtLink to="/" class="hover:underline">
            {{ $t('nav.requests') }}
          </NuxtLink>
          <NuxtLink v-if="me.roles.includes('finance_director')" to="/reference" class="hover:underline">
            {{ $t('nav.reference') }}
          </NuxtLink>
        </nav>
        <!-- The icon of a narrow screen stands on the right edge of the page content, not its button. -->
        <div class="ml-auto flex items-center gap-3 text-sm max-sm:-mr-2">
          <!-- The name and the roles do not fit the one line of a narrow screen. -->
          <div class="text-right max-sm:hidden">
            <div>{{ me.name }}</div>
            <div class="text-muted-foreground text-xs">
              {{ me.roles.map(role => $t(`role.${role}`)).join(', ') }}
            </div>
          </div>
          <!-- With notifications a narrow screen gets one icon that opens both them and the sign-out:
               its bar has no room for two. -->
          <template v-if="me.notifications.enabled">
            <Button
              as-child
              variant="ghost"
              size="icon"
              class="max-sm:hidden"
              :aria-label="$t('nav.notifications')"
              :title="$t('nav.notifications')"
            >
              <NuxtLink to="/notifications">
                <BellIcon />
              </NuxtLink>
            </Button>
            <SignOutButton variant="ghost" class="max-sm:hidden" />
            <!-- The menu renders no element of its own to carry a class, so a wrapper hides it on a wide screen. -->
            <div class="sm:hidden">
              <AccountMenu :me="me" />
            </div>
          </template>
          <SignOutButton v-else variant="ghost" compact />
        </div>
      </div>
    </header>
    <main class="mx-auto max-w-7xl px-4 py-6 max-sm:py-5">
      <slot />
    </main>
  </div>

  <p v-else class="text-muted-foreground p-6 text-sm">
    {{ $t('common.loading') }}
  </p>
</template>
