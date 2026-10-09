<script setup lang="ts">
import { CheckIcon, PaperclipIcon, XIcon } from '@lucide/vue'
import { toast } from 'vue-sonner'

const { t, locale } = useI18n()
const route = useRoute()
const api = useApi()
const format = useFormat()
const showFailure = useFailureToast()
const fieldMessages = useFieldMessages()

const id = route.params.id as string
const { data: request, error, reload } = useLoad(() => api<ExpenseRequestDetail>(`/requests/${id}`))

// The journal reads from the first entry to the last.
const journal = computed(() =>
  [...request.value!.journal].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id),
)

/** The entry that brought the request to its current status: it carries the reason. */
const lastChange = computed(() => journal.value.filter(entry => entry.status_changed).at(-1))

// --- Where the request is on its way ---

const holder = computed(() => holderOf(request.value!.status))

const steps = computed(() => {
  const { status } = request.value!
  if (status === 'rejected') {
    return []
  }
  // The finance director is on the way only of a request the moderator passed on.
  const viaDirector = status === 'escalated' || journal.value.some(entry => entry.status === 'escalated')
  const way = WAY.filter(party => party !== 'finance_director' || viaDirector)
  const at = holder.value ? way.indexOf(holder.value) : way.length
  return way.map((party, index) => ({ party, state: index < at ? 'done' : index === at ? 'current' : 'ahead' }))
})

/** The deadline has passed while the request is still on its way. */
const overdue = computed(() => {
  const { deadline } = request.value!
  return deadline !== null && holder.value !== undefined && deadline < new Date().toLocaleDateString('sv')
})

// --- Actions: the buttons come from the `actions` list of the server ---

// One action moves the request forward; the ones that stop it stay out of the way.
const FORWARD: Action[] = ['approve', 'pay', 'resubmit']
const STOPPING: Action[] = ['reject', 'cancel']

const forward = computed(() => request.value!.actions.filter(action => FORWARD.includes(action)))
const sideways = computed(() => request.value!.actions.filter(action => !FORWARD.includes(action) && !STOPPING.includes(action)))
const stopping = computed(() => request.value!.actions.filter(action => STOPPING.includes(action)))

// Actions a person may take at any time: they do not make the request wait for that person.
const AT_WILL: Action[] = ['cancel', 'reassign', 'finish']

/** The request waits for the person looking: the server offers them an action that moves it. */
const myTurn = computed(() =>
  // A recurring request paid for this period can be paid again, yet it waits for nobody.
  !request.value!.next_payment_from && request.value!.actions.some(action => !AT_WILL.includes(action)))

const panelTitle = computed(() => {
  const { status, author, moderator, payer, rejected_as, rejected_by, next_payment_from } = request.value!
  if (myTurn.value) {
    return t(`request.turn.${status}`)
  }
  if (status === 'rejected' && rejected_as) {
    return t(`request.rejected.${rejected_as}`, { name: rejected_by?.name })
  }
  if (!holder.value) {
    return t(`status.${status}`)
  }
  if (next_payment_from) {
    return t('request.at.nextPayment', { day: format.day(next_payment_from) })
  }
  if (holder.value === 'payer') {
    return payer ? t('request.at.payerNamed', { name: payer.name }) : t('request.at.payer')
  }
  const name = holder.value === 'author' ? author.name : moderator.name
  return t(`request.at.${holder.value}`, { name })
})

function actionLabel(action: Action): string {
  if (action === 'approve') {
    // The moderator approves a new request, the finance director one passed on to them.
    return request.value!.status === 'escalated' ? t('action.approveEscalated') : t('action.approveNew')
  }
  return t(`action.${action}`)
}

const editing = ref(false)

const pending = ref<Action>()
const actionComment = ref('')
const paidOn = ref('')
const paidAmount = ref('')
const payerId = ref('')
const actionErrors = ref<Record<string, string>>({})
const sending = ref(false)

// Approving may name the payer and reassigning does name one: these two actions ask who pays.
const NAMES_PAYER: Action[] = ['approve', 'reassign']

// The payers are asked for when the first such action is opened, and kept for the next one.
const payers = shallowRef<Person[]>()
const payerChoices = computed(() => withCurrent(payers.value ?? [], request.value!.payer))

/**
 * What the empty choice of a payer is called. An approval cannot take the payer away, so a
 * request that has one offers no empty choice there; reassigning may leave it to any payer.
 */
const noPayerLabel = computed(() =>
  pending.value === 'reassign' || !request.value!.payer ? t('request.anyPayer') : undefined)

async function ask(action: Action) {
  pending.value = action
  actionComment.value = ''
  paidOn.value = ''
  // The agreed amount, to be corrected when the bill of this period differs.
  paidAmount.value = typedAmount(request.value!.amount, locale.value)
  payerId.value = request.value!.payer ? String(request.value!.payer.id) : ''
  actionErrors.value = {}
  if (NAMES_PAYER.includes(action) && !payers.value) {
    try {
      payers.value = await api<Person[]>('/users', { query: { role: 'payer' } })
    }
    catch (failure) {
      showFailure(failure)
    }
  }
}

/** The payer an action sends: reassigning always says who, approving only when somebody is chosen. */
function payerOf(action: Action): number | null | undefined {
  const chosen = payerId.value === '' ? null : Number(payerId.value)
  if (action === 'reassign') {
    return chosen
  }
  return action === 'approve' && chosen !== null ? chosen : undefined
}

async function apply() {
  const action = pending.value!
  sending.value = true
  actionErrors.value = {}
  try {
    request.value = await api<ExpenseRequestDetail>(`/requests/${id}/${action}`, {
      method: 'POST',
      body: {
        comment: actionComment.value.trim() || undefined,
        paid_on: action === 'pay' ? paidOn.value || undefined : undefined,
        amount: action === 'pay' ? parseAmount(paidAmount.value, locale.value) || undefined : undefined,
        payer_id: payerOf(action),
      },
    })
    pending.value = undefined
  }
  catch (failure) {
    const byField = fieldMessages(failure)
    const current = conflictStatus(failure)
    if (byField) {
      actionErrors.value = byField
    }
    else if (current) {
      // Somebody acted first: say where the request is now and show it as it is.
      toast.error(t('request.statusConflict', { status: t(`status.${current}`) }))
      pending.value = undefined
      await reload()
    }
    else {
      showFailure(failure)
    }
  }
  finally {
    sending.value = false
  }
}

// --- Comment without a change of status ---

const comment = ref('')
const commentError = ref<string>()

async function addComment() {
  commentError.value = undefined
  try {
    request.value = await api<ExpenseRequestDetail>(`/requests/${id}/comments`, {
      method: 'POST',
      body: { comment: comment.value },
    })
    comment.value = ''
  }
  catch (failure) {
    const byField = fieldMessages(failure)
    if (byField) {
      commentError.value = byField.comment
    }
    else {
      showFailure(failure)
    }
  }
}

// --- Payment documents ---

async function upload(files: File[]) {
  for (const file of files) {
    const body = new FormData()
    body.append('file', file)
    try {
      await api<Attachment>(`/requests/${id}/attachments`, { method: 'POST', body })
    }
    catch (failure) {
      const limit = attachmentLimit(failure)
      const current = conflictStatus(failure)
      if (limit !== undefined) {
        toast.error(t('request.namedFileTooLarge', { name: file.name, limit: format.fileSize(limit) }))
      }
      else if (current) {
        toast.error(t('request.statusConflict', { status: t(`status.${current}`) }))
      }
      else {
        showFailure(failure)
      }
    }
  }
  await reload()
}

async function removeAttachment(attachment: Attachment) {
  try {
    await api(`/requests/${id}/attachments/${attachment.id}`, { method: 'DELETE' })
  }
  catch (failure) {
    const current = conflictStatus(failure)
    if (current) {
      toast.error(t('request.statusConflict', { status: t(`status.${current}`) }))
    }
    else {
      showFailure(failure)
    }
  }
  await reload()
}

/** The stage a journal entry brought the request to. Only the request knows who its rejection came from. */
function stageOf(entry: JournalEntry): RequestStage {
  return entry === lastChange.value ? RequestStage.of(request.value!) : RequestStage.ofStatus(entry.status)
}
</script>

<template>
  <p v-if="error && !request" class="text-muted-foreground text-sm">
    {{ apiStatus(error) === 404 ? $t('request.notFound') : $t('common.failed') }}
  </p>
  <p v-else-if="!request" class="text-muted-foreground text-sm">
    {{ $t('common.loading') }}
  </p>

  <div v-else class="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
    <!-- The request: what a person reads before deciding. -->
    <div class="grid gap-6">
      <div class="grid gap-3">
        <div class="flex flex-wrap items-center gap-3">
          <h1 class="text-xl font-semibold">
            {{ $t('request.title', { id: request.id }) }}
          </h1>
          <StatusBadge :stage="RequestStage.of(request)" />
          <!-- A returned request has this button in the panel, next to the reason of the return. -->
          <Button
            v-if="request.can_edit && request.status !== 'returned'"
            variant="outline"
            size="sm"
            class="ml-auto"
            @click="editing = true"
          >
            {{ $t('request.edit') }}
          </Button>
        </div>
        <div>
          <p class="text-3xl font-semibold tabular-nums">
            {{ format.amount(request.amount, request.currency) }}
          </p>
          <p class="text-muted-foreground mt-1 flex flex-wrap items-center gap-x-1.5 text-sm">
            <ReferenceValue :item="request.operation_type" />
            <RecurrenceMark v-if="request.recurrence" :recurrence="request.recurrence" />
            <span v-if="request.payment_period">· {{ request.payment_period }}</span>
          </p>
        </div>
        <ol v-if="steps.length > 0" class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <li v-for="(step, index) in steps" :key="step.party" class="flex items-center gap-2">
            <span v-if="index > 0" class="bg-border h-px w-4" aria-hidden="true" />
            <span
              class="flex items-center gap-1.5"
              :class="{
                'text-emerald-700': step.state === 'done',
                'text-primary font-medium': step.state === 'current',
                'text-muted-foreground': step.state === 'ahead',
              }"
              :aria-current="step.state === 'current' ? 'step' : undefined"
            >
              <CheckIcon v-if="step.state === 'done'" class="size-3.5" />
              <span
                v-else
                class="size-2 rounded-full"
                :class="step.state === 'current' ? 'bg-primary ring-primary/20 ring-3' : 'bg-border'"
              />
              {{ $t(`request.step.${step.party}`) }}
            </span>
          </li>
        </ol>
      </div>
      <RequestDialog v-model:open="editing" :request="request" @saved="saved => request = saved" />

      <div class="grid gap-4">
        <div>
          <h2 class="text-muted-foreground text-xs">
            {{ $t('field.situation') }}
          </h2>
          <p class="max-w-3xl whitespace-pre-wrap">
            {{ request.situation }}
          </p>
        </div>
        <div>
          <h2 class="text-muted-foreground text-xs">
            {{ $t('field.solution') }}
          </h2>
          <p class="max-w-3xl whitespace-pre-wrap">
            {{ request.solution }}
          </p>
        </div>
      </div>

      <dl class="grid grid-cols-2 gap-x-8 gap-y-4 border-t pt-6 sm:grid-cols-3">
        <div>
          <dt class="text-muted-foreground text-xs">
            {{ $t('field.priority') }}
          </dt>
          <dd>
            <ReferenceValue :item="request.priority" />
          </dd>
        </div>
        <div v-if="request.deadline">
          <dt class="text-muted-foreground text-xs">
            {{ $t('field.deadline') }}
          </dt>
          <dd :class="{ 'text-destructive font-medium': overdue }">
            {{ format.date(request.deadline) }}
          </dd>
        </div>
        <div v-if="request.payment_form">
          <dt class="text-muted-foreground text-xs">
            {{ $t('field.paymentForm') }}
          </dt>
          <dd>
            <ReferenceValue :item="request.payment_form" />
          </dd>
        </div>
        <div>
          <dt class="text-muted-foreground text-xs">
            {{ $t('field.author') }}
          </dt>
          <dd>{{ request.author.name }}</dd>
        </div>
        <div>
          <dt class="text-muted-foreground text-xs">
            {{ $t('field.moderator') }}
          </dt>
          <dd>{{ request.moderator.name }}</dd>
        </div>
        <div v-if="request.payer">
          <dt class="text-muted-foreground text-xs">
            {{ $t('field.payer') }}
          </dt>
          <dd>{{ request.payer.name }}</dd>
        </div>
        <div>
          <dt class="text-muted-foreground text-xs">
            {{ $t('field.createdAt') }}
          </dt>
          <dd>{{ format.dateTime(request.created_at) }}</dd>
        </div>
      </dl>

      <section v-if="request.payments.length > 0" class="grid gap-3 border-t pt-6">
        <h2 class="font-semibold">
          {{ $t('request.payments') }}
        </h2>
        <RequestPayments :payments="request.payments" :currency="request.currency" />
      </section>

      <section class="grid gap-3 border-t pt-6">
        <h2 class="font-semibold">
          {{ $t('field.attachments') }}
        </h2>
        <p v-if="request.attachments.length === 0 && !request.can_edit" class="text-muted-foreground text-sm">
          {{ $t('request.noAttachments') }}
        </p>
        <ul v-if="request.attachments.length > 0" class="grid gap-1.5 text-sm">
          <li v-for="attachment in request.attachments" :key="attachment.id" class="flex items-center gap-2">
            <PaperclipIcon class="text-muted-foreground size-4 shrink-0" />
            <a
              :href="`/api/v1/requests/${request.id}/attachments/${attachment.id}`"
              class="text-primary truncate underline-offset-4 hover:underline"
              download
            >{{ attachment.filename }}</a>
            <span class="text-muted-foreground shrink-0 text-xs">{{ format.fileSize(attachment.size) }}</span>
            <Button
              v-if="request.can_edit"
              variant="ghost"
              size="icon-xs"
              :aria-label="$t('request.removeFile')"
              @click="removeAttachment(attachment)"
            >
              <XIcon />
            </Button>
          </li>
        </ul>
        <!-- Documents are added and removed here; the edit dialog holds only the fields. -->
        <FileDropzone v-if="request.can_edit" id="attachment" @files="upload" />
      </section>
    </div>

    <!-- The decision: whose turn it is, what they can do, and what has happened so far. -->
    <aside class="grid gap-6 lg:sticky lg:top-6">
      <section
        class="grid gap-3 rounded-xl border p-4"
        :class="{
          'border-primary/30 bg-primary/5': myTurn && request.status !== 'returned',
          'border-orange-300 bg-orange-50': request.status === 'returned',
          'border-emerald-200 bg-emerald-50': request.status === 'paid',
          'bg-muted/50': !myTurn && request.status !== 'returned' && request.status !== 'paid',
        }"
      >
        <h2 class="font-semibold">
          {{ panelTitle }}
        </h2>
        <p v-if="request.status === 'paid' && request.payer && request.paid_on" class="text-sm">
          {{ $t('request.paidBy', { date: format.date(request.paid_on), name: request.payer.name }) }}
        </p>
        <!-- Why the request came back or was refused, in the words of the person who decided. -->
        <p
          v-if="(request.status === 'returned' || request.status === 'rejected') && lastChange?.comment"
          class="text-sm whitespace-pre-wrap"
        >
          <span class="font-medium">{{ lastChange.person.name }}:</span> {{ lastChange.comment }}
        </p>
        <p v-if="myTurn && request.status === 'returned'" class="text-sm">
          {{ $t('request.fixHint') }}
        </p>

        <div v-if="forward.length > 0 || sideways.length > 0" class="grid gap-2">
          <!-- A request that waits for nobody keeps its action, without the weight of a call. -->
          <Button
            v-for="action in forward"
            :key="action"
            :variant="myTurn ? 'default' : 'outline'"
            :class="{ 'bg-background': !myTurn }"
            @click="ask(action)"
          >
            {{ actionLabel(action) }}
          </Button>
          <Button
            v-if="request.status === 'returned' && request.can_edit"
            variant="outline"
            class="bg-background"
            @click="editing = true"
          >
            {{ $t('request.edit') }}
          </Button>
          <Button
            v-for="action in sideways"
            :key="action"
            variant="outline"
            class="bg-background"
            @click="ask(action)"
          >
            {{ actionLabel(action) }}
          </Button>
        </div>
        <div v-if="stopping.length > 0" class="flex justify-center">
          <Button
            v-for="action in stopping"
            :key="action"
            variant="ghost"
            size="sm"
            class="text-destructive hover:text-destructive"
            @click="ask(action)"
          >
            {{ actionLabel(action) }}
          </Button>
        </div>
      </section>

      <section class="grid gap-3">
        <h2 class="font-semibold">
          {{ $t('request.journal') }}
        </h2>
        <ol class="grid gap-4">
          <li v-for="entry in journal" :key="entry.id" class="grid grid-cols-[0.5rem_minmax(0,1fr)] gap-x-3 text-sm">
            <span
              class="mt-1.5 size-2 rounded-full"
              :class="entry.status_changed ? stageOf(entry).paint.dot : 'bg-border'"
              aria-hidden="true"
            />
            <div class="grid gap-0.5">
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span class="font-medium">{{ entry.person.name }}</span>
                <StatusBadge v-if="entry.status_changed" :stage="stageOf(entry)" />
              </div>
              <p v-if="entry.payer_changed">
                {{ entry.payer ? $t('request.payerSet', { name: entry.payer.name }) : $t('request.payerCleared') }}
              </p>
              <p v-if="entry.comment" class="whitespace-pre-wrap">
                {{ entry.comment }}
              </p>
              <p class="text-muted-foreground text-xs">
                {{ format.dateTime(entry.created_at) }}
              </p>
            </div>
          </li>
        </ol>

        <form class="mt-2 grid gap-2 border-t pt-4" novalidate @submit.prevent="addComment">
          <FormField id="comment" :label="$t('request.comment')" :error="commentError">
            <Textarea id="comment" v-model="comment" :aria-invalid="commentError ? true : undefined" />
          </FormField>
          <Button type="submit" variant="outline" class="w-fit">
            {{ $t('request.addComment') }}
          </Button>
        </form>
      </section>
    </aside>

    <Dialog :open="pending !== undefined" @update:open="open => { if (!open) pending = undefined }">
      <DialogContent v-if="pending" :show-close-button="false">
        <form class="grid gap-4" novalidate @submit.prevent="apply">
          <DialogHeader>
            <DialogTitle>{{ actionLabel(pending) }}</DialogTitle>
            <DialogDescription>
              {{ $t('request.title', { id: request.id }) }} · {{ format.amount(request.amount, request.currency) }}
            </DialogDescription>
          </DialogHeader>
          <FormField
            v-if="pending === 'pay'"
            id="paid-on"
            :label="$t('field.paidOn')"
            required
            :error="actionErrors.paid_on"
          >
            <Input id="paid-on" v-model="paidOn" type="date" class="w-fit" required />
          </FormField>
          <FormField
            v-if="pending === 'pay'"
            id="paid-amount"
            :label="$t('field.paidAmount')"
            required
            :error="actionErrors.amount"
          >
            <div class="flex w-56">
              <Input
                id="paid-amount"
                v-model="paidAmount"
                inputmode="decimal"
                class="rounded-r-none text-right tabular-nums"
                required
                :aria-invalid="actionErrors.amount ? true : undefined"
              />
              <span class="border-input bg-muted/50 text-muted-foreground -ml-px flex h-8 shrink-0 items-center rounded-r-lg border px-2.5 text-sm">{{ request.currency }}</span>
            </div>
          </FormField>
          <FormField
            v-if="NAMES_PAYER.includes(pending)"
            id="action-payer"
            :label="$t('field.payer')"
            :error="actionErrors.payer_id"
          >
            <PersonSelect id="action-payer" v-model="payerId" :people="payerChoices" :empty-label="noPayerLabel" />
          </FormField>
          <FormField id="action-comment" :label="$t('request.commentOptional')" :error="actionErrors.comment">
            <Textarea id="action-comment" v-model="actionComment" rows="3" />
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" @click="pending = undefined">
              {{ $t('request.dismiss') }}
            </Button>
            <Button type="submit" :variant="STOPPING.includes(pending) ? 'destructive' : 'default'" :disabled="sending">
              {{ actionLabel(pending) }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </div>
</template>
