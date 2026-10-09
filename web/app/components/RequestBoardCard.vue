<script setup lang="ts">
// A request on the board. Each reference list has its own corner: the operation type top left,
// the priority top right, the payment form next to the amount, so the cards of a column read alike.
// A card that waits for the person looking is tinted with an opaque colour: its column is painted too.
const props = defineProps<{
  request: ExpenseRequest
  /** The request waits for the person looking. */
  mine: boolean
}>()

const format = useFormat()
const overdue = computed(() => isOverdue(props.request, calendarDay()))
// Who pays is named only while the request waits for the payment.
const payer = computed(() => holderOf(props.request.status) === 'payer' ? props.request.payer : null)
</script>

<template>
  <NuxtLink
    :to="`/requests/${request.id}`"
    class="grid grid-cols-1 gap-2 rounded-lg border p-3 transition-colors"
    :class="mine ? 'border-primary/40 bg-[color-mix(in_oklab,var(--primary)_6%,var(--background))]' : 'bg-background hover:border-foreground/25'"
  >
    <div class="text-muted-foreground flex items-center justify-between gap-3 text-xs">
      <ReferenceValue :item="request.operation_type" />
      <ReferenceValue :item="request.priority" />
    </div>
    <p class="line-clamp-2 leading-snug font-medium">
      {{ gist(request) }}
    </p>
    <div class="text-muted-foreground flex items-center justify-between gap-3 text-xs">
      <span class="text-foreground text-base font-semibold tabular-nums">{{ format.amount(request.amount, request.currency) }}</span>
      <ReferenceValue v-if="request.payment_form" :item="request.payment_form" />
    </div>
    <!-- How often the request is paid and, once it is paid for this period, when it comes back. -->
    <p v-if="request.recurrence" class="text-muted-foreground flex items-center gap-1.5 text-xs">
      <RecurrenceMark :recurrence="request.recurrence" />
      <span v-if="request.next_payment_from" class="truncate">
        · {{ $t('board.nextPayment', { day: format.day(request.next_payment_from) }) }}
      </span>
    </p>
    <div class="text-muted-foreground flex items-center justify-between gap-3 text-xs">
      <!-- A long name gives way, the number does not: it is what people call the request by. -->
      <span class="flex min-w-0">
        <span class="truncate">
          <template v-if="mine"><span class="text-primary font-medium">{{ $t('holder.you') }}</span> · </template>{{ request.author.name }}
        </span>
        <span class="shrink-0 whitespace-pre"> · {{ $t('board.number', { id: request.id }) }}</span>
      </span>
      <span v-if="request.deadline" class="shrink-0" :class="{ 'text-destructive font-medium': overdue }">
        {{ $t('board.until', { day: format.day(request.deadline) }) }}
      </span>
    </div>
    <p v-if="payer && !mine" class="text-muted-foreground truncate text-xs">
      {{ $t('board.payer', { name: payer.name }) }}
    </p>
  </NuxtLink>
</template>
