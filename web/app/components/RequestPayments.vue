<script setup lang="ts">
// The payments of a request as the server gives them, the latest first: when, how much, by whom.
defineProps<{
  payments: Payment[]
  /** The currency of the request: a payment has no other. */
  currency: string
}>()

const format = useFormat()
</script>

<template>
  <ul class="divide-y rounded-lg border text-sm">
    <li v-for="payment in payments" :key="payment.id" class="flex flex-wrap items-baseline gap-x-4 gap-y-0.5 px-3 py-2">
      <span class="w-28 shrink-0">{{ format.date(payment.paid_on) }}</span>
      <span class="font-medium tabular-nums">{{ format.amount(payment.amount, currency) }}</span>
      <span class="text-muted-foreground ml-auto">{{ payment.person.name }}</span>
    </li>
  </ul>
</template>
