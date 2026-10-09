<script setup lang="ts">
import { XIcon } from '@lucide/vue'

// The statuses in one row, each with the number of requests the person may see in it: the
// status filter of a narrow screen. None chosen means all of them; the chosen one is cleared
// by a second press. The row loads its own numbers.
const status = defineModel<Status>()

const api = useApi()
const showFailure = useFailureToast()

const { data, error, reload } = useLoad(() => api<RequestTotals[]>('/request-totals'))
watch(error, value => value && showFailure(value))
defineExpose({ reload })

// The way of a request first, the statuses it does not leave after it.
const ORDER = [...STATUSES_ON_THE_WAY, ...FINAL_STATUSES]
</script>

<template>
  <!-- The row is longer than the screen and runs to its edge: the status cut by the edge says there are more. -->
  <div
    class="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    role="group"
    :aria-label="$t('field.status')"
  >
    <button
      v-for="value in ORDER"
      :key="value"
      type="button"
      class="flex h-8 shrink-0 items-center gap-1.5 rounded-lg border px-2.5 text-sm transition-colors"
      :class="{ 'bg-primary/10 border-primary/30 text-primary font-medium': status === value }"
      :aria-pressed="status === value"
      @click="status = status === value ? undefined : value"
    >
      {{ $t(`status.${value}`) }}
      <span class="tabular-nums" :class="status === value ? 'text-primary/70' : 'text-muted-foreground'">
        {{ data?.find(entry => entry.status === value)?.count }}
      </span>
      <XIcon v-if="status === value" class="-mr-0.5 size-3.5" />
    </button>
  </div>
</template>
