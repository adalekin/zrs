<script setup lang="ts">
import { RepeatIcon } from '@lucide/vue'

// Says that a request is paid every period, and how often. A request paid once has no mark.
defineProps<{ recurrence: Recurrence }>()
</script>

<template>
  <span class="text-muted-foreground inline-flex items-center gap-1 text-xs font-normal whitespace-nowrap">
    <RepeatIcon class="size-3" aria-hidden="true" />{{ $t(`recurrence.${recurrence}`) }}
  </span>
</template>
