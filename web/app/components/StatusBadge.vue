<script setup lang="ts">
import { CheckIcon, XIcon } from '@lucide/vue'

// The name of the status in the colour of the stage. The stage owns the colour.
defineProps<{ stage: RequestStage }>()
</script>

<template>
  <span
    class="inline-flex h-5 items-center gap-1 rounded-full px-2 text-xs font-medium whitespace-nowrap"
    :class="stage.paint.badge"
  >
    <CheckIcon v-if="stage.status === 'paid'" class="size-3" :stroke-width="2.5" />
    <XIcon v-else-if="stage.status === 'rejected'" class="size-3" :stroke-width="2.5" />
    {{ $t(`status.${stage.status}`) }}
  </span>
</template>
