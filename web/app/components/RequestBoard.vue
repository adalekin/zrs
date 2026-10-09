<script setup lang="ts">
// The requests on their way as columns by status. The board loads its own data: the cards of a
// column come from the list of requests, the counts and the sums from the totals, both filtered
// on the server by what the person may see. It changes nothing: a card opens its request.
const props = defineProps<{
  /** Only the requests that wait for the person looking. */
  awaitingMe: boolean
  /** The requests that wait for the person looking, to mark their cards. */
  waitingIds: Set<number>
  /** One order for every column. */
  sort: RequestSort
}>()

const api = useApi()
const format = useFormat()
const showFailure = useFailureToast()

// The API gives at most this many requests in one answer. A longer column says how many it left out.
const COLUMN_SIZE = 100

const { data, error, reload } = useLoad(async () => {
  const queue = props.awaitingMe ? true : undefined
  const [totals, finished, ...pages] = await Promise.all([
    api<RequestTotals[]>('/request-totals', { query: { awaiting_me: queue } }),
    // Finished requests wait for nobody, so their numbers under the board never follow the queue.
    props.awaitingMe ? api<RequestTotals[]>('/request-totals') : undefined,
    ...STATUSES_ON_THE_WAY.map(status => api<ExpenseRequestPage>('/requests', {
      query: { status, awaiting_me: queue, sort: props.sort, size: COLUMN_SIZE },
    })),
  ])
  const of = (entries: RequestTotals[], status: Status) => entries.find(entry => entry.status === status)!
  return {
    columns: STATUSES_ON_THE_WAY.map((status, index) => ({
      status,
      requests: pages[index]!.items,
      totals: of(totals, status),
    })),
    finished: FINAL_STATUSES.map(status => of(finished ?? totals, status)),
  }
})
watch(() => [props.awaitingMe, props.sort], reload)
watch(error, value => value && showFailure(value))
defineExpose({ reload })

/** Where the rest of a long column is read: the list with the same requests. */
function listOf(status: Status) {
  return props.awaitingMe ? { query: { awaiting_me: 'true' } } : { query: { view: 'all', status } }
}
</script>

<template>
  <p v-if="!data" class="text-muted-foreground text-sm">
    {{ error ? $t('common.failed') : $t('common.loading') }}
  </p>

  <div v-else class="grid gap-4">
    <div class="grid grid-cols-2 items-start gap-4 lg:grid-cols-4">
      <section
        v-for="column in data.columns"
        :key="column.status"
        class="grid grid-cols-1 gap-2 rounded-xl p-2"
        :class="RequestStage.ofStatus(column.status).paint.column"
      >
        <header class="grid gap-0.5 px-1 pt-1 pb-0.5">
          <div class="flex items-center gap-2">
            <StatusBadge :stage="RequestStage.ofStatus(column.status)" />
            <span class="text-muted-foreground text-xs tabular-nums">{{ column.totals.count }}</span>
            <span class="ml-auto text-right text-xs font-medium tabular-nums">
              {{ column.totals.amounts.map(total => format.amount(total.amount, total.currency)).join(' + ') }}
            </span>
          </div>
          <p class="text-muted-foreground text-xs">
            {{ $t(`board.at.${holderOf(column.status)}`) }}
          </p>
        </header>
        <RequestBoardCard
          v-for="request in column.requests"
          :key="request.id"
          :request="request"
          :mine="awaitingMe || waitingIds.has(request.id)"
        />
        <p v-if="column.totals.count === 0" class="text-muted-foreground rounded-lg border border-dashed px-3 py-6 text-center text-xs">
          {{ $t('board.empty') }}
        </p>
        <NuxtLink
          v-if="column.totals.count > column.requests.length"
          :to="listOf(column.status)"
          class="text-primary px-1 py-1 text-xs underline-offset-4 hover:underline"
        >
          {{ $t('board.more', { count: column.totals.count - column.requests.length }) }}
        </NuxtLink>
      </section>
    </div>

    <div class="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-2 border-t pt-4 text-sm">
      <span>{{ $t('board.finished') }}</span>
      <NuxtLink
        v-for="totals in data.finished"
        :key="totals.status"
        :to="{ query: { view: 'all', status: totals.status } }"
        class="hover:text-foreground flex items-center gap-1.5 tabular-nums"
      >
        <StatusBadge :stage="RequestStage.ofStatus(totals.status)" />{{ totals.count }}
      </NuxtLink>
    </div>
  </div>
</template>
