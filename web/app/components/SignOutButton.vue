<script setup lang="ts">
import { LogOutIcon } from '@lucide/vue'

defineProps<{
  variant: 'outline' | 'ghost'
  /** A narrow screen gets the icon instead of the word: for the top bar, where the word does not fit. */
  compact?: boolean
}>()
</script>

<template>
  <!-- A form post, not a link: the browser does not send the session cookie with a
       post from another site, so nobody can sign the person out from outside. -->
  <form method="post" action="/sign-out">
    <Button type="submit" :variant="variant" size="sm">
      <LogOutIcon v-if="compact" class="sm:hidden" />
      <span :class="{ 'max-sm:sr-only': compact }">{{ $t('nav.signOut') }}</span>
    </Button>
  </form>
</template>
