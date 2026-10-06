<script setup lang="ts">
import { XIcon } from '@lucide/vue'
import { DialogClose } from 'reka-ui'
import { toast } from 'vue-sonner'

// The one place where a request is written: a new one from the list, an existing one
// from its page.
const props = defineProps<{ request?: ExpenseRequestDetail }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{
  created: []
  saved: [request: ExpenseRequestDetail]
}>()

const { t } = useI18n()
const form = useTemplateRef('form')
// Chosen files outlive a closed dialog, like the text of the draft does.
const files = ref<File[]>([])

// The author edits a returned request to answer this comment, so it stays in sight.
const returned = computed(() => {
  if (props.request?.status !== 'returned') {
    return undefined
  }
  return props.request.journal
    .filter(entry => entry.status === 'returned' && entry.status_changed && entry.comment)
    .sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id)[0]
})

/** A click past the edge of the dialog does not close what somebody has started. */
function keepStarted(event: Event) {
  if (form.value?.dirty) {
    event.preventDefault()
  }
}

async function finish(saved: ExpenseRequestDetail, failedFiles: string[]) {
  open.value = false
  if (props.request) {
    emit('saved', saved)
    return
  }
  if (failedFiles.length > 0) {
    // The page of the request is where the documents can be added again.
    toast.error(t('request.filesFailed', { id: saved.id, files: failedFiles.join(', ') }))
    await navigateTo(`/requests/${saved.id}`)
    return
  }
  toast.success(t('request.created', { id: saved.id, moderator: saved.moderator.name }), {
    action: { label: t('request.open'), onClick: () => navigateTo(`/requests/${saved.id}`) },
  })
  emit('created')
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent
      class="flex max-h-[calc(100dvh-2rem)] flex-col gap-0 overflow-hidden p-0 max-sm:h-dvh max-sm:max-h-none max-sm:max-w-none max-sm:rounded-none sm:max-w-2xl"
      :show-close-button="false"
      :aria-describedby="undefined"
      @interact-outside="keepStarted"
    >
      <DialogHeader class="flex-row items-center justify-between border-b px-4 py-3 sm:px-6">
        <DialogTitle>
          {{ request ? $t('request.editTitle', { id: request.id }) : $t('request.createTitle') }}
        </DialogTitle>
        <DialogClose as-child>
          <Button variant="ghost" size="icon-sm" class="-mr-1.5" :aria-label="$t('common.close')">
            <XIcon />
          </Button>
        </DialogClose>
      </DialogHeader>
      <p v-if="returned" class="border-b bg-amber-50 px-4 py-3 text-sm whitespace-pre-wrap text-amber-950 sm:px-6">
        <span class="font-medium">{{ $t('request.returnedBy', { name: returned.person.name }) }}</span>
        {{ returned.comment }}
      </p>
      <RequestForm
        ref="form"
        v-model:files="files"
        :request="request"
        autofocus
        @saved="finish"
        @dismiss="open = false"
      />
    </DialogContent>
  </Dialog>
</template>
