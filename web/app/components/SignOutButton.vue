<script setup lang="ts">
defineProps<{ variant: 'outline' | 'ghost' }>()
</script>

<template>
  <!-- A form post, not a link: the browser does not send the session cookie with a
       post from another site, so nobody can sign the person out from outside. -->
  <form method="post" action="/sign-out">
    <Button type="submit" :variant="variant" size="sm">
      {{ $t('nav.signOut') }}
    </Button>
  </form>
</template>
