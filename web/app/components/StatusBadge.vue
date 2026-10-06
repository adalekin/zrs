<script setup lang="ts">
import { CheckIcon, XIcon } from '@lucide/vue'

defineProps<{ status: Status }>()

// Colour goes to the statuses where somebody has to act, one hue per party.
// Finished requests stay quiet.
const TONES: Record<Status, string> = {
  new: 'bg-blue-50 text-blue-700',
  escalated: 'bg-violet-50 text-violet-700',
  approved: 'bg-emerald-50 text-emerald-700',
  returned: 'bg-amber-100 text-amber-800',
  paid: 'bg-muted text-muted-foreground',
  rejected: 'bg-muted text-muted-foreground',
}
</script>

<template>
  <span
    class="inline-flex h-5 items-center gap-1 rounded-full px-2 text-xs font-medium whitespace-nowrap"
    :class="TONES[status]"
  >
    <CheckIcon v-if="status === 'paid'" class="size-3 text-emerald-600" />
    <XIcon v-else-if="status === 'rejected'" class="size-3 text-red-600" />
    {{ $t(`status.${status}`) }}
  </span>
</template>
