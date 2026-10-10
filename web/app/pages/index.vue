<script setup lang="ts">
import { ArrowUpDownIcon, Columns3Icon, ListIcon } from '@lucide/vue'

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

// What this person left on the page in this browser: see the watcher of the address below.
const memory = new RequestViewMemory(() => localStorage, me.value!.id)

// The tab, the layout, the order, the status filter and the page number live in the address of the page.
// A narrow screen has one layout: a column of the board there would be the list filtered by a status.
const narrow = useNarrow()
const layout = computed<'list' | 'board'>(() => route.query.layout === 'board' && !narrow.value ? 'board' : 'list')
const sort = computed<RequestSort>(() => {
  const asked = REQUEST_SORTS.find(value => value === route.query.sort)
  if (layout.value === 'board') {
    // An order the board does not offer is not replaced by a similar one: the board goes by its own.
    return asked && BOARD_SORTS.includes(asked) ? asked : BOARD_SORT
  }
  return asked ?? LIST_SORT
})
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

// The list loads only while it is the layout on the screen: the board loads its own data.
const { data, error, reload } = useLoad(async () => view.value && layout.value === 'list'
  ? await api<ExpenseRequestPage>('/requests', {
      query: {
        awaiting_me: view.value === 'queue' ? true : undefined,
        status: view.value === 'all' ? status.value : undefined,
        sort: sort.value,
        page: page.value,
      },
    })
  : undefined)
watch([view, layout, status, sort, page], reload)
watch(error, value => value && showFailure(value))

const pages = computed(() => data.value ? Math.max(1, Math.ceil(data.value.total / data.value.size)) : 1)

/**
 * Changes the address. The tab, the layout and the order stay unless the change names them;
 * the status filter and the page number go, so that any change starts from the first page.
 */
function show(change: { awaiting_me?: string, view?: string, layout?: string, sort?: string, status?: string, page?: string }) {
  const { awaiting_me, view, layout, sort } = route.query
  const query = { awaiting_me, view, layout, sort, ...change }
  // A choice that leaves nothing set is a choice too: the page is back as it opens by itself, and nothing brings the old view back.
  if (!RequestView.named(query)) {
    memory.forget()
  }
  router.replace({ query })
}

function setStatus(value: Status | undefined) {
  show({ awaiting_me: undefined, view: 'all', status: value })
}

const statusChoice = computed({
  get: () => status.value ?? '',
  set: value => setStatus(value || undefined),
})

function turnTo(target: number) {
  show({ status: status.value, page: target > 1 ? String(target) : undefined })
}

/** The order goes to the address; the order a layout has by itself is not written there. */
function setSort(value: RequestSort) {
  const own = layout.value === 'board' ? BOARD_SORT : LIST_SORT
  show({ sort: value === own ? undefined : value, status: status.value })
}

const sortChoice = computed({
  get: () => sort.value,
  set: value => setSort(value),
})

// The two layouts have different orders by themselves and offer different ones, so each opens with its own.
function setLayout(value: 'list' | 'board') {
  show({ layout: value === 'board' ? 'board' : undefined, sort: undefined })
}

// An address may carry an order the board does not offer. The board ignores it, and the address says so.
watch([layout, () => route.query.sort], () => {
  if (layout.value === 'board' && route.query.sort !== undefined && route.query.sort !== sort.value) {
    show({ sort: undefined })
  }
}, { immediate: true })

// The page remembers how it was left. An address that names a view is shown as it is, and what it
// names becomes what is remembered. An address that names none is filled from what this person left in
// this browser: so open the link of the section and a new visit.
watch(() => route.query, (query) => {
  const named = RequestView.named(query)
  if (named) {
    memory.keep(named)
    return
  }
  const left = memory.recall()
  if (left) {
    router.replace({ query: { ...query, ...left.toQuery() } })
  }
}, { immediate: true })

const creating = ref(false)
const board = useTemplateRef('board')
const strip = useTemplateRef('strip')

function created() {
  recount()
  strip.value?.reload()
  if (layout.value === 'board') {
    board.value?.reload()
  }
  else {
    reload()
  }
}

/** Who has the request now: the person looking, when the request is in their queue. */
function who(request: ExpenseRequest) {
  return view.value === 'queue' || waitingIds.value.has(request.id)
    ? { text: t('holder.you'), mine: true }
    : holder(request)
}

const today = calendarDay()
</script>

<template>
  <div class="grid gap-4 max-sm:gap-3">
    <!-- One row on a wide screen. A narrow one gets two that stand on the edges of the cards: the title with the order and the new request, then the tabs. -->
    <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
      <h1 class="text-xl font-semibold max-sm:flex-1">
        {{ $t('requests.title') }}
      </h1>
      <!-- A narrow screen shows the two tabs as one switch of its whole width. -->
      <div
        class="flex gap-1 max-sm:order-2 max-sm:grid max-sm:w-full max-sm:grid-cols-2 max-sm:gap-0 max-sm:rounded-lg max-sm:border max-sm:p-0.5"
        role="tablist"
      >
        <button
          type="button"
          role="tab"
          class="flex h-8 items-center gap-1.5 rounded-lg px-3 text-sm transition-colors max-sm:h-7 max-sm:justify-center max-sm:rounded-md"
          :class="view === 'queue' ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:bg-muted'"
          :aria-selected="view === 'queue'"
          @click="show({ awaiting_me: 'true', view: undefined })"
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
          class="flex h-8 items-center rounded-lg px-3 text-sm transition-colors max-sm:h-7 max-sm:justify-center max-sm:rounded-md"
          :class="view === 'all' ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:bg-muted'"
          :aria-selected="view === 'all'"
          @click="show({ awaiting_me: undefined, view: 'all' })"
        >
          {{ $t('requests.all') }}
        </button>
      </div>
      <div class="flex items-center gap-2 max-sm:hidden">
        <!-- The queue is defined by its statuses, and on the board the statuses are the columns: the filter belongs to the list of everything. -->
        <NativeSelect v-if="layout === 'list' && view === 'all'" v-model="statusChoice" :aria-label="$t('field.status')">
          <NativeSelectOption value="">
            {{ $t('requests.allStatuses') }}
          </NativeSelectOption>
          <NativeSelectOption v-for="value in STATUSES" :key="value" :value="value">
            {{ $t(`status.${value}`) }}
          </NativeSelectOption>
        </NativeSelect>
        <!-- One order for all the columns of the board. The list is sorted by the headings of its table. -->
        <template v-if="layout === 'board'">
          <span class="text-muted-foreground text-sm" aria-hidden="true">
            {{ $t('requests.sort.label') }}
          </span>
          <NativeSelect v-model="sortChoice" :aria-label="$t('requests.sort.label')">
            <NativeSelectOption v-for="value in BOARD_SORTS" :key="value" :value="value">
              {{ $t(sortLabel(value)) }}
            </NativeSelectOption>
          </NativeSelect>
        </template>
      </div>
      <div class="ml-auto flex items-center gap-2 sm:gap-3">
        <!-- The cards have no headings to sort by: an icon opens every order by its name.
             It is tinted while the order is not the one the list opens with. -->
        <label
          v-if="layout === 'list'"
          class="has-[:focus-visible]:ring-ring/50 relative flex size-8 items-center justify-center rounded-lg border has-[:focus-visible]:ring-3 xl:hidden"
          :class="{ 'bg-primary/10 border-primary/30 text-primary': sort !== LIST_SORT }"
        >
          <ArrowUpDownIcon class="size-4" />
          <select v-model="sortChoice" class="absolute inset-0 opacity-0" :aria-label="$t('requests.sort.label')">
            <option v-for="value in LIST_SORTS" :key="value" :value="value">
              {{ $t(sortLabel(value)) }}
            </option>
          </select>
        </label>
        <div class="flex rounded-lg border p-0.5 max-sm:hidden" role="group" :aria-label="$t('requests.layout.label')">
          <button
            v-for="option in (['list', 'board'] as const)"
            :key="option"
            type="button"
            class="flex h-7 items-center gap-1.5 rounded-md px-2.5 text-sm transition-colors"
            :class="layout === option ? 'bg-muted font-medium' : 'text-muted-foreground hover:text-foreground'"
            :aria-pressed="layout === option"
            @click="setLayout(option)"
          >
            <ListIcon v-if="option === 'list'" class="size-4" />
            <Columns3Icon v-else class="size-4" />
            {{ $t(`requests.layout.${option}`) }}
          </button>
        </div>
        <Button v-if="me?.roles.includes('requester')" @click="creating = true">
          {{ $t('requests.create') }}
        </Button>
      </div>
    </div>
    <!-- The statuses with their numbers stand in for the status filter and for the columns of the board. -->
    <RequestStatusStrip v-if="narrow && view === 'all'" ref="strip" :model-value="status" @update:model-value="setStatus" />
    <RequestDialog v-model:open="creating" @created="created" />

    <template v-if="layout === 'board'">
      <RequestBoard v-if="view" ref="board" :awaiting-me="view === 'queue'" :waiting-ids="waitingIds" :sort="sort" />
      <p v-else class="text-muted-foreground text-sm">
        {{ $t('common.loading') }}
      </p>
    </template>

    <p v-else-if="!data" class="text-muted-foreground text-sm">
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
      <!-- The table has nine columns and fits a screen of 1280 px. A narrower one shows the same rows
           as cards: one column on a phone, two and three on wider screens. -->
      <ul class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:hidden">
        <li v-for="request in data.items" :key="request.id">
          <!-- One column that may shrink: a long first line wraps instead of pushing the card wider than the screen.
               The cards of one row are of one height, each with its lines at the top. -->
          <NuxtLink
            :to="`/requests/${request.id}`"
            class="grid h-full grid-cols-1 content-start gap-1.5 rounded-xl border p-3"
            :class="[RequestStage.of(request).paint.row, { 'text-muted-foreground': RequestStage.of(request).quiet }]"
          >
            <div class="flex items-baseline justify-between gap-3">
              <span class="line-clamp-2 min-w-0 font-medium">{{ gist(request) }}</span>
              <span class="shrink-0 font-medium tabular-nums">{{ format.amount(request.amount, request.currency) }}</span>
            </div>
            <div class="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              <ReferenceValue v-for="item in marks(request)" :key="item.id" :item="item" />
              <RecurrenceMark v-if="request.recurrence" :recurrence="request.recurrence" />
              <!-- The deadline as the table and the board show it: marked once it has passed. -->
              <span
                v-if="request.deadline"
                class="ml-auto shrink-0"
                :class="{ 'text-destructive font-medium': isOverdue(request, today) }"
              >
                {{ $t('board.until', { day: format.day(request.deadline) }) }}
              </span>
            </div>
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
              <StatusBadge :stage="RequestStage.of(request)" />
              <span v-if="who(request)" :class="who(request)!.mine ? 'text-primary font-medium' : 'text-muted-foreground'">
                {{ who(request)!.text }}
              </span>
              <span class="text-muted-foreground ml-auto">
                {{ request.author.name }} · {{ $t('field.id') }} {{ request.id }}
              </span>
            </div>
          </NuxtLink>
        </li>
      </ul>

      <Table class="max-xl:hidden">
        <TableHeader>
          <TableRow>
            <TableHead class="w-14">
              {{ $t('field.id') }}
            </TableHead>
            <TableHead>{{ $t('field.request') }}</TableHead>
            <TableHead>{{ $t('field.operationType') }}</TableHead>
            <TableHead>
              <SortHeader :state="sortState(sort, 'priority')" @sort="setSort(nextSort(sort, 'priority'))">
                {{ $t('field.priority') }}
              </SortHeader>
            </TableHead>
            <TableHead class="text-right">
              {{ $t('field.amount') }}
            </TableHead>
            <!-- Right after the amount: how much and how to pay read together. -->
            <TableHead>{{ $t('field.paymentForm') }}</TableHead>
            <TableHead>{{ $t('field.status') }}</TableHead>
            <TableHead>
              <SortHeader :state="sortState(sort, 'deadline')" @sort="setSort(nextSort(sort, 'deadline'))">
                {{ $t('field.deadline') }}
              </SortHeader>
            </TableHead>
            <TableHead>
              <SortHeader :state="sortState(sort, 'created')" @sort="setSort(nextSort(sort, 'created'))">
                {{ $t('field.submittedAt') }}
              </SortHeader>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="request in data.items"
            :key="request.id"
            class="cursor-pointer"
            :class="[RequestStage.of(request).paint.row, { 'text-muted-foreground': RequestStage.of(request).quiet }]"
            @click="navigateTo(`/requests/${request.id}`)"
          >
            <TableCell class="text-muted-foreground tabular-nums">
              {{ request.id }}
            </TableCell>
            <!-- The name takes the room the other columns leave, and never less than it needs to be read:
                 with long values around it the table scrolls sideways instead of squeezing the name out. -->
            <TableCell class="w-full max-w-0 min-w-56">
              <NuxtLink :to="`/requests/${request.id}`" class="block truncate font-medium hover:underline" @click.stop>
                {{ gist(request) }}
              </NuxtLink>
              <!-- The author is named in every row, the reader's own too: the rows of a list are of one height. -->
              <p class="text-muted-foreground truncate">
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
              <p v-if="request.recurrence" class="mt-0.5">
                <RecurrenceMark :recurrence="request.recurrence" />
              </p>
            </TableCell>
            <TableCell class="text-muted-foreground text-xs">
              <ReferenceValue v-if="request.payment_form" :item="request.payment_form" />
            </TableCell>
            <TableCell class="whitespace-nowrap">
              <StatusBadge :stage="RequestStage.of(request)" />
              <p
                v-if="who(request)"
                class="mt-0.5 text-xs"
                :class="who(request)!.mine ? 'text-primary font-medium' : 'text-muted-foreground'"
              >
                {{ who(request)!.text }}
              </p>
            </TableCell>
            <TableCell class="whitespace-nowrap" :class="isOverdue(request, today) ? 'text-destructive font-medium' : 'text-muted-foreground'">
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
