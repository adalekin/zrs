<script setup lang="ts">
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const api = useApi()
const me = useMe()
const format = useFormat()
const showFailure = useFailureToast()
const holder = useHolder()

// The service sends no notifications: a person learns what waits for them from this
// page. So the queue is the first tab, and it opens by itself when it has requests.
const { data: queue, error: waitingError, reload: recount } = useLoad(() =>
  api<ExpenseRequestPage>('/requests', { query: { awaiting_me: true, size: 100 } }),
)
watch(waitingError, value => value && showFailure(value))
const waiting = computed(() => queue.value?.total)
// Which rows of the other tab wait for this person too. The server decides that;
// a queue longer than one page of the API marks its first hundred.
const waitingIds = computed(() => new Set(queue.value?.items.map(request => request.id)))

// The tab, the status filter and the page number live in the address of the page.
const status = computed(() => STATUSES.find(value => value === route.query.status))
const page = computed(() => {
  const value = Number(route.query.page)
  return Number.isInteger(value) && value > 0 ? value : 1
})
const view = computed<'queue' | 'all' | undefined>(() => {
  if (route.query.awaiting_me === 'true') {
    return 'queue'
  }
  if (route.query.view === 'all' || status.value || waitingError.value) {
    return 'all'
  }
  // No tab in the address: the queue when it has requests, everything otherwise.
  if (waiting.value === undefined) {
    return undefined
  }
  return waiting.value > 0 ? 'queue' : 'all'
})

const { data, error, reload } = useLoad(async () => view.value
  ? await api<ExpenseRequestPage>('/requests', {
      query: {
        awaiting_me: view.value === 'queue' ? true : undefined,
        status: view.value === 'all' ? status.value : undefined,
        page: page.value,
      },
    })
  : undefined)
watch([view, status, page], reload)
watch(error, value => value && showFailure(value))

const pages = computed(() => data.value ? Math.max(1, Math.ceil(data.value.total / data.value.size)) : 1)

function show(query: { awaiting_me?: string, view?: string, status?: string, page?: string }) {
  router.replace({ query })
}

const statusChoice = computed({
  get: () => status.value ?? '',
  // A changed filter starts from the first page.
  set: value => show({ view: 'all', status: value || undefined }),
})

function turnTo(target: number) {
  show({ ...route.query, page: target > 1 ? String(target) : undefined })
}

const creating = ref(false)

function created() {
  recount()
  reload()
}

/** Who has the request now: the person looking, when the request is in their queue. */
function who(request: ExpenseRequest) {
  return view.value === 'queue' || waitingIds.value.has(request.id)
    ? { text: t('holder.you'), mine: true }
    : holder(request)
}

// The calendar day of the browser, in the form the API writes dates.
const today = new Date().toLocaleDateString('sv')

/** A deadline that has passed while the request is still on its way. */
function overdue(request: ExpenseRequest) {
  return request.deadline !== null && holderOf(request.status) !== undefined && request.deadline < today
}

/** The first line of the situation: what the request is about. */
const gist = (request: ExpenseRequest) => request.situation.split('\n', 1)[0]

/** The reference values of a request in the order a card shows them; a request may have no payment form. */
const marks = (request: ExpenseRequest) =>
  [request.operation_type, request.priority, request.payment_form].filter(item => item !== null)
</script>

<template>
  <div class="grid gap-4">
    <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
      <h1 class="text-xl font-semibold">
        {{ $t('requests.title') }}
      </h1>
      <div class="flex gap-1" role="tablist">
        <button
          type="button"
          role="tab"
          class="flex h-8 items-center gap-1.5 rounded-lg px-3 text-sm transition-colors"
          :class="view === 'queue' ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:bg-muted'"
          :aria-selected="view === 'queue'"
          @click="show({ awaiting_me: 'true' })"
        >
          {{ $t('requests.awaitingMe') }}
          <span
            v-if="waiting"
            class="rounded-full px-1.5 text-xs tabular-nums"
            :class="view === 'queue' ? 'bg-primary text-primary-foreground' : 'bg-primary/10 text-primary font-medium'"
          >{{ waiting }}</span>
        </button>
        <button
          type="button"
          role="tab"
          class="flex h-8 items-center rounded-lg px-3 text-sm transition-colors"
          :class="view === 'all' ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:bg-muted'"
          :aria-selected="view === 'all'"
          @click="show({ view: 'all' })"
        >
          {{ $t('requests.all') }}
        </button>
      </div>
      <!-- The queue is defined by its statuses, so the filter belongs to the other tab. -->
      <NativeSelect v-if="view === 'all'" v-model="statusChoice" :aria-label="$t('field.status')">
        <NativeSelectOption value="">
          {{ $t('requests.allStatuses') }}
        </NativeSelectOption>
        <NativeSelectOption v-for="value in STATUSES" :key="value" :value="value">
          {{ $t(`status.${value}`) }}
        </NativeSelectOption>
      </NativeSelect>
      <Button v-if="me?.roles.includes('requester')" class="ml-auto" @click="creating = true">
        {{ $t('requests.create') }}
      </Button>
    </div>
    <RequestDialog v-model:open="creating" @created="created" />

    <p v-if="!data" class="text-muted-foreground text-sm">
      {{ error ? $t('common.failed') : $t('common.loading') }}
    </p>

    <div
      v-else-if="data.items.length === 0"
      class="grid justify-items-center gap-3 rounded-xl border border-dashed px-4 py-16 text-center"
    >
      <template v-if="view === 'queue'">
        <p class="font-medium">
          {{ $t('requests.queueEmpty') }}
        </p>
        <p class="text-muted-foreground text-sm">
          {{ $t('requests.queueEmptyHint') }}
        </p>
      </template>
      <template v-else-if="status">
        <p class="font-medium">
          {{ $t('requests.noneInStatus', { status: $t(`status.${status}`) }) }}
        </p>
      </template>
      <template v-else>
        <p class="font-medium">
          {{ $t('requests.empty') }}
        </p>
        <template v-if="me?.roles.includes('requester')">
          <p class="text-muted-foreground text-sm">
            {{ $t('requests.emptyHint') }}
          </p>
          <Button @click="creating = true">
            {{ $t('requests.create') }}
          </Button>
        </template>
      </template>
    </div>

    <template v-else>
      <!-- A phone shows the same rows as cards: the table does not fit. -->
      <ul class="grid grid-cols-1 gap-2 sm:hidden">
        <li v-for="request in data.items" :key="request.id">
          <!-- One column that may shrink: a long first line wraps instead of pushing the card wider than the screen. -->
          <NuxtLink :to="`/requests/${request.id}`" class="grid grid-cols-1 gap-1.5 rounded-xl border p-3">
            <div class="flex items-baseline justify-between gap-3">
              <span class="line-clamp-2 min-w-0 font-medium">{{ gist(request) }}</span>
              <span class="shrink-0 font-medium tabular-nums">{{ format.amount(request.amount, request.currency) }}</span>
            </div>
            <div class="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              <ReferenceValue v-for="item in marks(request)" :key="item.id" :item="item" />
            </div>
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
              <StatusBadge :status="request.status" />
              <span v-if="who(request)" :class="who(request)!.mine ? 'text-primary font-medium' : 'text-muted-foreground'">
                {{ who(request)!.text }}
              </span>
              <span class="text-muted-foreground ml-auto">
                <template v-if="request.author.id !== me?.id">{{ request.author.name }} · </template>{{ $t('field.id') }} {{ request.id }}
              </span>
            </div>
          </NuxtLink>
        </li>
      </ul>

      <Table class="max-sm:hidden">
        <TableHeader>
          <TableRow>
            <TableHead class="w-14">
              {{ $t('field.id') }}
            </TableHead>
            <TableHead>{{ $t('field.request') }}</TableHead>
            <TableHead>{{ $t('field.operationType') }}</TableHead>
            <TableHead>{{ $t('field.priority') }}</TableHead>
            <TableHead class="text-right">
              {{ $t('field.amount') }}
            </TableHead>
            <!-- Right after the amount: how much and how to pay read together. -->
            <TableHead>{{ $t('field.paymentForm') }}</TableHead>
            <TableHead>{{ $t('field.status') }}</TableHead>
            <TableHead>{{ $t('field.deadline') }}</TableHead>
            <TableHead>{{ $t('field.submittedAt') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="request in data.items"
            :key="request.id"
            class="cursor-pointer"
            @click="navigateTo(`/requests/${request.id}`)"
          >
            <TableCell class="text-muted-foreground tabular-nums">
              {{ request.id }}
            </TableCell>
            <TableCell class="max-w-0 w-full">
              <NuxtLink :to="`/requests/${request.id}`" class="block truncate font-medium hover:underline" @click.stop>
                {{ gist(request) }}
              </NuxtLink>
              <!-- A person who sees only their own requests does not need their own name in every row. -->
              <p v-if="request.author.id !== me?.id" class="text-muted-foreground truncate">
                {{ request.author.name }}
              </p>
            </TableCell>
            <TableCell class="text-muted-foreground text-xs">
              <ReferenceValue :item="request.operation_type" />
            </TableCell>
            <TableCell class="text-muted-foreground text-xs">
              <ReferenceValue :item="request.priority" />
            </TableCell>
            <TableCell class="text-right font-medium whitespace-nowrap tabular-nums">
              {{ format.amount(request.amount, request.currency) }}
            </TableCell>
            <TableCell class="text-muted-foreground text-xs">
              <ReferenceValue v-if="request.payment_form" :item="request.payment_form" />
            </TableCell>
            <TableCell class="whitespace-nowrap">
              <StatusBadge :status="request.status" />
              <p
                v-if="who(request)"
                class="mt-0.5 text-xs"
                :class="who(request)!.mine ? 'text-primary font-medium' : 'text-muted-foreground'"
              >
                {{ who(request)!.text }}
              </p>
            </TableCell>
            <TableCell class="whitespace-nowrap" :class="overdue(request) ? 'text-destructive font-medium' : 'text-muted-foreground'">
              {{ request.deadline ? format.day(request.deadline) : '' }}
            </TableCell>
            <TableCell class="text-muted-foreground whitespace-nowrap">
              {{ format.day(request.created_at) }}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <div v-if="pages > 1" class="flex items-center gap-3 text-sm">
        <Button variant="outline" size="sm" :disabled="page <= 1" @click="turnTo(page - 1)">
          {{ $t('requests.previous') }}
        </Button>
        <span>{{ $t('requests.page', { page, pages }) }}</span>
        <Button variant="outline" size="sm" :disabled="page >= pages" @click="turnTo(page + 1)">
          {{ $t('requests.next') }}
        </Button>
      </div>
    </template>
  </div>
</template>
