<script setup lang="ts">
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon } from '@lucide/vue'

// The heading of a column the list can be sorted by. It only shows the order and reports a click:
// which order follows a click is decided in utils/request-sort.ts.
defineProps<{
  /** Not sorted by this column, sorted in the order of a first click, or turned over. */
  state: 'none' | 'first' | 'turned'
}>()
defineEmits<{ sort: [] }>()
</script>

<template>
  <button
    type="button"
    class="hover:text-primary flex items-center gap-0.5 font-medium"
    :aria-pressed="state !== 'none'"
    @click="$emit('sort')"
  >
    <slot />
    <ArrowUpDownIcon v-if="state === 'none'" class="text-muted-foreground/50 size-3" />
    <ArrowDownIcon v-else-if="state === 'first'" class="text-primary size-3" />
    <ArrowUpIcon v-else class="text-primary size-3" />
  </button>
</template>
