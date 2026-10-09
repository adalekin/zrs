<script setup lang="ts">
import { CheckIcon, SendIcon } from '@lucide/vue'

// Where a person links their Telegram chat to get messages about requests. Whether the chat is
// linked is what the server says in GET /me: the page keeps no copy of it and asks again after
// every change.
const api = useApi()
const me = useMe()
const showFailure = useFailureToast()

// How often the page asks whether the bot was started, while a link waits for it.
const ASK_EVERY_MS = 3000

const link = ref<TelegramLinkCode>()
const busy = ref(false)
let asking: ReturnType<typeof setInterval> | undefined

async function refresh() {
  me.value = await api<Me>('/me')
}

function stopAsking() {
  clearInterval(asking)
  asking = undefined
}

async function getLink() {
  busy.value = true
  try {
    link.value = await api<TelegramLinkCode>('/telegram-link-codes', { method: 'POST' })
    stopAsking()
    asking = setInterval(async () => {
      await refresh()
      if (me.value!.notifications.telegram_linked || new Date(link.value!.expires_at) <= new Date()) {
        stopAsking()
        link.value = undefined
      }
    }, ASK_EVERY_MS)
  }
  catch (failure) {
    showFailure(failure)
  }
  busy.value = false
}

async function unlink() {
  busy.value = true
  try {
    await api('/telegram-link', { method: 'DELETE' })
    await refresh()
  }
  catch (failure) {
    showFailure(failure)
  }
  busy.value = false
}

onBeforeUnmount(stopAsking)
</script>

<template>
  <div class="grid max-w-xl gap-4">
    <h1 class="text-xl font-semibold">
      {{ $t('notifications.title') }}
    </h1>

    <p v-if="!me!.notifications.enabled" class="text-muted-foreground text-sm">
      {{ $t('notifications.off') }}
    </p>

    <section v-else class="grid gap-4 rounded-xl border p-4">
      <div class="grid gap-1">
        <h2 class="flex items-center gap-2 font-semibold">
          Telegram
          <span
            v-if="me!.notifications.telegram_linked"
            class="inline-flex h-5 items-center gap-1 rounded-full bg-green-100 px-2 text-xs font-medium text-green-800"
          >
            <CheckIcon class="size-3" />{{ $t('notifications.linked') }}
          </span>
        </h2>
        <p class="text-muted-foreground text-sm">
          {{ $t('notifications.about') }}
        </p>
      </div>

      <Button
        v-if="me!.notifications.telegram_linked"
        variant="outline"
        class="w-fit"
        :disabled="busy"
        @click="unlink"
      >
        {{ $t('notifications.unlink') }}
      </Button>

      <template v-else-if="link">
        <Button as-child class="w-fit">
          <a :href="link.url" target="_blank" rel="noopener">
            <SendIcon />{{ $t('notifications.open') }}
          </a>
        </Button>
        <p class="text-muted-foreground text-sm">
          {{ $t('notifications.linkHint') }}
        </p>
      </template>

      <Button v-else class="w-fit" :disabled="busy" @click="getLink">
        {{ $t('notifications.link') }}
      </Button>
    </section>
  </div>
</template>
