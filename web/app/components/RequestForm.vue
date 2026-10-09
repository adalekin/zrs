<script setup lang="ts">
import { XIcon } from '@lucide/vue'

// One form for a new request and for the edit of an existing one, shown in RequestDialog.
const props = defineProps<{
  request?: ExpenseRequestDetail
  /** Put the cursor into the first empty required field once the lists are loaded. */
  autofocus?: boolean
}>()
const emit = defineEmits<{
  /** `failedFiles` names the documents of a new request that did not upload. */
  saved: [request: ExpenseRequestDetail, failedFiles: string[]]
  dismiss: []
}>()

const { t, locale } = useI18n()
const api = useApi()
const me = useMe()
const format = useFormat()
const showFailure = useFailureToast()
const fieldMessages = useFieldMessages()

/** Field values as the API takes them; an empty choice or an empty date is null. */
interface Payload {
  operation_type_id: number | null
  moderator_id: number | null
  situation: string
  solution: string
  amount: string
  currency: string
  payment_period: string
  payment_form_id: number | null
  priority_id: number | null
  deadline: string | null
  payer_id: number | null
}

type Fields = Record<keyof Payload, string>

const { request } = props

// What the form starts from: the fields of the request under edit or, for a new
// request, empty ones. A list with one choice adds that choice to a new request.
const baseline: Fields = reactive(request
  ? {
      operation_type_id: String(request.operation_type.id),
      moderator_id: String(request.moderator.id),
      situation: request.situation,
      solution: request.solution,
      amount: typedAmount(request.amount, locale.value),
      currency: request.currency,
      payment_period: request.payment_period,
      payment_form_id: request.payment_form ? String(request.payment_form.id) : '',
      priority_id: String(request.priority.id),
      deadline: request.deadline ?? '',
      payer_id: request.payer ? String(request.payer.id) : '',
    }
  : {
      operation_type_id: '',
      moderator_id: '',
      situation: '',
      solution: '',
      amount: '',
      currency: '',
      payment_period: '',
      payment_form_id: '',
      priority_id: '',
      deadline: '',
      payer_id: '',
    })

// Unfinished input survives a closed dialog and a reloaded page: it is kept in the
// storage of the browser tab until it is sent or cleared.
const draftKey = `zrs:request-draft:${me.value!.id}:${request ? request.id : 'new'}`

function readDraft(): Partial<Fields> {
  try {
    return JSON.parse(sessionStorage.getItem(draftKey) ?? '{}')
  }
  catch {
    // The browser may refuse the storage; the form then works without a draft.
    return {}
  }
}

function writeDraft(fields: Fields | null) {
  try {
    if (fields) {
      sessionStorage.setItem(draftKey, JSON.stringify(fields))
    }
    else {
      sessionStorage.removeItem(draftKey)
    }
  }
  catch {
    // See readDraft.
  }
}

const form: Fields = reactive({ ...baseline, ...readDraft() })

const idOrNull = (value: string) => value === '' ? null : Number(value)

function payload(fields: Fields): Payload {
  return {
    operation_type_id: idOrNull(fields.operation_type_id),
    moderator_id: idOrNull(fields.moderator_id),
    situation: fields.situation,
    solution: fields.solution,
    amount: parseAmount(fields.amount, locale.value),
    currency: fields.currency,
    payment_period: fields.payment_period,
    payment_form_id: idOrNull(fields.payment_form_id),
    priority_id: idOrNull(fields.priority_id),
    deadline: fields.deadline === '' ? null : fields.deadline,
    payer_id: idOrNull(fields.payer_id),
  }
}

const initial = payload(baseline)

const { data: lists, error: listsError } = useLoad(async () => {
  const [operationTypes, paymentForms, priorities, moderators, payers] = await Promise.all([
    api<ReferenceItem[]>('/reference-items', { query: { kind: 'operation_type', is_active: true } }),
    api<ReferenceItem[]>('/reference-items', { query: { kind: 'payment_form', is_active: true } }),
    api<ReferenceItem[]>('/reference-items', { query: { kind: 'priority', is_active: true } }),
    api<Person[]>('/users', { query: { role: 'moderator' } }),
    api<Person[]>('/users', { query: { role: 'payer' } }),
  ])
  return { operationTypes, paymentForms, priorities, moderators, payers }
})
watch(listsError, value => value && showFailure(value))

const operationTypes = computed(() => withCurrent(lists.value?.operationTypes ?? [], request?.operation_type))
const paymentForms = computed(() => withCurrent(lists.value?.paymentForms ?? [], request?.payment_form))
const priorities = computed(() => withCurrent(lists.value?.priorities ?? [], request?.priority))
const moderators = computed(() => withCurrent(
  // Nobody moderates their own request.
  (lists.value?.moderators ?? []).filter(person => person.id !== me.value?.id),
  request?.moderator,
))
const payers = computed(() => withCurrent(lists.value?.payers ?? [], request?.payer))
const currencies = computed(() => {
  const list = me.value?.currencies ?? []
  // A request keeps its currency after the installation drops it from the list.
  return request && !list.includes(request.currency) ? [request.currency, ...list] : list
})

// What keeps a request from being submitted at all, said before the person starts typing.
const blockers = computed(() => {
  if (!lists.value) {
    return []
  }
  return [
    operationTypes.value.length === 0 && t('request.blocked.operationType'),
    priorities.value.length === 0 && t('request.blocked.priority'),
    moderators.value.length === 0 && t('request.blocked.moderator'),
  ].filter(reason => reason !== false)
})

const formElement = useTemplateRef('formElement')

watch(lists, async () => {
  if (!request) {
    const choices: [keyof Fields, string[]][] = [
      ['operation_type_id', operationTypes.value.map(item => String(item.id))],
      ['priority_id', priorities.value.map(item => String(item.id))],
      ['moderator_id', moderators.value.map(person => String(person.id))],
      ['currency', currencies.value],
    ]
    for (const [field, values] of choices) {
      // A draft may hold a choice that has left the list since.
      if (!values.includes(form[field])) {
        form[field] = ''
      }
      // A required list with one choice leaves nothing to choose.
      if (values.length === 1) {
        baseline[field] = values[0]!
        if (form[field] === '') {
          form[field] = values[0]!
        }
      }
    }
    if (form.payment_form_id !== '' && !paymentForms.value.some(item => String(item.id) === form.payment_form_id)) {
      form.payment_form_id = ''
    }
    if (form.payer_id !== '' && !payers.value.some(person => String(person.id) === form.payer_id)) {
      form.payer_id = ''
    }
  }
  if (props.autofocus) {
    await nextTick()
    const required = formElement.value!.querySelectorAll<HTMLInputElement>('[aria-required="true"]')
    Array.from(required).find(control => control.value === '')?.focus()
  }
})

// --- Payment documents of a new request: uploaded right after the request is created ---

// The dialog keeps the chosen files while it is closed; a page reload drops them.
const files = defineModel<File[]>('files', { default: () => [] })
// --- The draft ---

const typed = computed(() =>
  Object.keys(baseline).some(key => form[key as keyof Fields] !== baseline[key as keyof Fields]),
)
const dirty = computed(() => typed.value || files.value.length > 0)
defineExpose({ dirty })

watch(form, () => writeDraft(typed.value ? form : null))

function clear() {
  Object.assign(form, baseline)
  files.value = []
  errors.value = {}
  writeDraft(null)
}

// --- Sending ---

const errors = ref<Record<string, string>>({})
const sending = ref(false)
// What the button says while the request is on its way: an upload can take a while.
const progress = ref('')

// The error of a field goes away once the person changes the field.
watch(() => ({ ...form }), (now, before) => {
  for (const field of Object.keys(now) as (keyof Fields)[]) {
    if (now[field] !== before[field] && errors.value[field]) {
      errors.value = Object.fromEntries(Object.entries(errors.value).filter(([key]) => key !== field))
    }
  }
})

const invalid = (field: keyof Fields) => errors.value[field] ? true : undefined

const periodChoices = computed(() => [
  t('request.period.once'),
  t('request.period.monthly'),
  t('request.period.yearly'),
])

async function upload(id: number): Promise<string[]> {
  const failed: string[] = []
  for (const [index, file] of files.value.entries()) {
    progress.value = t('request.uploading', { done: index + 1, total: files.value.length })
    const body = new FormData()
    body.append('file', file)
    try {
      await api<Attachment>(`/requests/${id}/attachments`, { method: 'POST', body })
    }
    catch {
      // Whatever the reason, the request exists by now: the person is told which
      // documents to add again on the page of the request.
      failed.push(file.name)
    }
  }
  return failed
}

async function submit() {
  if (sending.value || !lists.value || blockers.value.length > 0) {
    return
  }
  sending.value = true
  progress.value = t('request.sending')
  errors.value = {}
  try {
    const values = payload(form)
    if (request) {
      // Only what the author changed is sent: untouched fields are not validated again.
      const changed = Object.fromEntries(
        Object.entries(values).filter(([field, value]) => value !== initial[field as keyof Payload]),
      )
      const saved = await api<ExpenseRequestDetail>(`/requests/${request.id}`, { method: 'PATCH', body: changed })
      writeDraft(null)
      emit('saved', saved, [])
    }
    else {
      const created = await api<ExpenseRequestDetail>('/requests', { method: 'POST', body: values })
      const failedFiles = await upload(created.id)
      clear()
      emit('saved', created, failedFiles)
    }
  }
  catch (error) {
    const byField = fieldMessages(error)
    if (byField) {
      // An empty amount is a missing field, not a wrong number.
      errors.value = byField.amount && form.amount.trim() === ''
        ? { ...byField, amount: t('error.field.required') }
        : byField
      await nextTick()
      const first = formElement.value!.querySelector<HTMLElement>('[aria-invalid="true"]')
      first?.focus()
      first?.scrollIntoView({ block: 'center' })
    }
    else {
      showFailure(error)
    }
  }
  finally {
    sending.value = false
  }
}
</script>

<template>
  <form
    ref="formElement"
    class="flex min-h-0 flex-col"
    novalidate
    @submit.prevent="submit"
    @keydown.meta.enter="submit"
    @keydown.ctrl.enter="submit"
  >
    <div class="grid min-h-0 gap-4 overflow-y-auto p-4 sm:grid-cols-6 sm:p-6">
      <div
        v-if="blockers.length > 0"
        class="border-destructive/30 bg-destructive/5 col-span-full grid gap-1 rounded-lg border p-3 text-sm"
        role="alert"
      >
        <p class="font-medium">
          {{ $t('request.blocked.title') }}
        </p>
        <p v-for="reason in blockers" :key="reason" class="text-muted-foreground">
          {{ reason }}
        </p>
      </div>

      <FormField
        id="operation-type"
        class="sm:col-span-3"
        :label="$t('field.operationType')"
        required
        :error="errors.operation_type_id"
      >
        <NativeSelect
          id="operation-type"
          v-model="form.operation_type_id"
          class="w-full"
          aria-required="true"
          :aria-invalid="invalid('operation_type_id')"
        >
          <NativeSelectOption value="">
            {{ $t('request.notChosen') }}
          </NativeSelectOption>
          <NativeSelectOption v-for="item in operationTypes" :key="item.id" :value="String(item.id)">
            {{ item.name }}
          </NativeSelectOption>
        </NativeSelect>
      </FormField>

      <FormField
        id="moderator"
        class="sm:col-span-3"
        :label="$t('field.moderator')"
        required
        :error="errors.moderator_id"
      >
        <PersonSelect
          id="moderator"
          v-model="form.moderator_id"
          :people="moderators"
          :empty-label="$t('request.notChosen')"
          aria-required="true"
          :aria-invalid="invalid('moderator_id')"
        />
      </FormField>

      <FormField
        id="situation"
        class="col-span-full"
        :label="$t('field.situation')"
        required
        :hint="$t('field.situationHint')"
        :error="errors.situation"
      >
        <Textarea
          id="situation"
          v-model="form.situation"
          class="max-h-48"
          aria-required="true"
          :aria-invalid="invalid('situation')"
        />
      </FormField>

      <FormField
        id="solution"
        class="col-span-full"
        :label="$t('field.solution')"
        required
        :hint="$t('field.solutionHint')"
        :error="errors.solution"
      >
        <Textarea
          id="solution"
          v-model="form.solution"
          class="max-h-48"
          aria-required="true"
          :aria-invalid="invalid('solution')"
        />
      </FormField>

      <FormField
        id="amount"
        class="sm:col-span-3"
        :label="$t('field.amount')"
        required
        :error="errors.amount ?? (errors.currency && $t('request.chooseCurrency'))"
      >
        <div class="flex">
          <Input
            id="amount"
            v-model="form.amount"
            class="rounded-r-none tabular-nums focus-visible:z-10 aria-invalid:z-10"
            inputmode="decimal"
            autocomplete="off"
            aria-required="true"
            :aria-invalid="invalid('amount')"
            @blur="form.amount = groupAmount(form.amount)"
          />
          <!-- One currency in the installation leaves nothing to choose. -->
          <span
            v-if="currencies.length === 1"
            class="border-input bg-muted/50 text-muted-foreground -ml-px flex h-8 shrink-0 items-center rounded-r-lg border px-2.5 text-sm"
          >{{ currencies[0] }}</span>
          <NativeSelect
            v-else
            v-model="form.currency"
            class="-ml-px shrink-0 focus-within:z-10 [&_select]:rounded-l-none"
            :aria-label="$t('field.currency')"
            aria-required="true"
            :aria-invalid="invalid('currency')"
          >
            <NativeSelectOption value="">
              {{ $t('field.currency') }}
            </NativeSelectOption>
            <NativeSelectOption v-for="code in currencies" :key="code" :value="code">
              {{ code }}
            </NativeSelectOption>
          </NativeSelect>
        </div>
      </FormField>

      <FormField
        id="payment-period"
        class="sm:col-span-3"
        :label="$t('field.paymentPeriod')"
        required
        :error="errors.payment_period"
      >
        <Input
          id="payment-period"
          v-model="form.payment_period"
          aria-required="true"
          :aria-invalid="invalid('payment_period')"
        />
        <!-- The usual answers in one click; the field stays free text. -->
        <div class="flex flex-wrap gap-1.5">
          <Button
            v-for="choice in periodChoices"
            :key="choice"
            type="button"
            variant="outline"
            size="xs"
            class="rounded-full font-normal"
            tabindex="-1"
            @click="form.payment_period = choice"
          >
            {{ choice }}
          </Button>
        </div>
      </FormField>

      <FormField
        id="payment-form"
        class="sm:col-span-3"
        :label="$t('field.paymentForm')"
        :error="errors.payment_form_id"
      >
        <NativeSelect
          id="payment-form"
          v-model="form.payment_form_id"
          class="w-full"
          :aria-invalid="invalid('payment_form_id')"
        >
          <NativeSelectOption value="">
            {{ $t('request.notChosen') }}
          </NativeSelectOption>
          <NativeSelectOption v-for="item in paymentForms" :key="item.id" :value="String(item.id)">
            {{ item.name }}
          </NativeSelectOption>
        </NativeSelect>
      </FormField>

      <!-- Who pays stands next to how it is paid. Nobody chosen leaves the request to any payer. -->
      <FormField id="payer" class="sm:col-span-3" :label="$t('field.payer')" :error="errors.payer_id">
        <PersonSelect
          id="payer"
          v-model="form.payer_id"
          :people="payers"
          :empty-label="$t('request.anyPayer')"
          :aria-invalid="invalid('payer_id')"
        />
      </FormField>

      <FormField
        id="priority"
        class="sm:col-span-3"
        :label="$t('field.priority')"
        required
        :error="errors.priority_id"
      >
        <NativeSelect
          id="priority"
          v-model="form.priority_id"
          class="w-full"
          aria-required="true"
          :aria-invalid="invalid('priority_id')"
        >
          <NativeSelectOption value="">
            {{ $t('request.notChosen') }}
          </NativeSelectOption>
          <NativeSelectOption v-for="item in priorities" :key="item.id" :value="String(item.id)">
            {{ item.name }}
          </NativeSelectOption>
        </NativeSelect>
      </FormField>

      <FormField id="deadline" class="sm:col-span-3" :label="$t('field.deadline')" :error="errors.deadline">
        <Input id="deadline" v-model="form.deadline" type="date" :aria-invalid="invalid('deadline')" />
      </FormField>

      <!-- The documents of an existing request are kept on its page. -->
      <div v-if="!request" class="col-span-full grid gap-1.5">
        <Label for="attachments">{{ $t('field.attachments') }}</Label>
        <FileDropzone id="attachments" @files="chosen => files.push(...chosen)" />
        <ul v-if="files.length > 0" class="grid gap-1 text-sm">
          <li v-for="(file, index) in files" :key="index" class="flex items-center gap-2">
            <span class="truncate">{{ file.name }}</span>
            <span class="text-muted-foreground shrink-0 text-xs">{{ format.fileSize(file.size) }}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              :aria-label="$t('request.removeFile')"
              @click="files.splice(index, 1)"
            >
              <XIcon />
            </Button>
          </li>
        </ul>
      </div>
    </div>

    <div class="bg-muted/50 flex items-center gap-2 border-t px-4 py-3 sm:px-6">
      <Button v-if="dirty" type="button" variant="ghost" @click="clear">
        {{ request ? $t('request.revert') : $t('request.clear') }}
      </Button>
      <Button type="button" variant="outline" class="ml-auto" @click="emit('dismiss')">
        {{ $t('request.dismiss') }}
      </Button>
      <Button type="submit" :disabled="sending || !lists || blockers.length > 0">
        {{ sending ? progress : request ? $t('request.save') : $t('request.submit') }}
      </Button>
    </div>
  </form>
</template>
