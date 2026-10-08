<script setup lang="ts">
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
      <div class="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <NuxtLink to="/" class="flex items-center gap-2 text-lg font-semibold">
          <AppLogo />
          ZRS
        </NuxtLink>
        <nav class="flex gap-4 text-sm">
          <NuxtLink to="/" class="hover:underline">
            {{ $t('nav.requests') }}
          </NuxtLink>
          <NuxtLink v-if="me.roles.includes('finance_director')" to="/reference" class="hover:underline">
            {{ $t('nav.reference') }}
          </NuxtLink>
        </nav>
        <div class="ml-auto flex items-center gap-3 text-sm">
          <div class="text-right">
            <div>{{ me.name }}</div>
            <div class="text-muted-foreground text-xs">
              {{ me.roles.map(role => $t(`role.${role}`)).join(', ') }}
            </div>
          </div>
          <SignOutButton variant="ghost" />
        </div>
      </div>
    </header>
    <main class="mx-auto max-w-7xl px-4 py-6">
      <slot />
    </main>
  </div>

  <p v-else class="text-muted-foreground p-6 text-sm">
    {{ $t('common.loading') }}
  </p>
</template>
