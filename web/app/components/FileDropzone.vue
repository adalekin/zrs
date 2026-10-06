<script setup lang="ts">
import { PaperclipIcon } from '@lucide/vue'
import { toast } from 'vue-sonner'

// Where payment documents are dropped or chosen. A file over the limit of the
// installation is refused here, before anything is sent.
defineProps<{ id: string }>()
const emit = defineEmits<{ files: [files: File[]] }>()

const { t } = useI18n()
const me = useMe()
const format = useFormat()

const dragging = ref(false)

function take(list: FileList | null | undefined) {
  const limit = me.value!.attachment_max_bytes
  const accepted: File[] = []
  for (const file of list ?? []) {
    if (file.size > limit) {
      toast.error(t('request.namedFileTooLarge', { name: file.name, limit: format.fileSize(limit) }))
    }
    else {
      accepted.push(file)
    }
  }
  if (accepted.length > 0) {
    emit('files', accepted)
  }
}

function pick(event: Event) {
  const input = event.target as HTMLInputElement
  take(input.files)
  input.value = ''
}

function drop(event: DragEvent) {
  dragging.value = false
  take(event.dataTransfer?.files)
}
</script>

<template>
  <label
    class="text-muted-foreground hover:bg-muted/50 focus-within:border-ring focus-within:ring-ring/50 flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed px-3 py-4 text-sm transition-colors focus-within:ring-3"
    :class="dragging && 'border-ring bg-muted/50'"
    @dragover.prevent="dragging = true"
    @dragleave="dragging = false"
    @drop.prevent="drop"
  >
    <PaperclipIcon class="size-4 shrink-0" />
    <span>
      {{ $t('request.dropFiles') }}
      <span class="text-xs">· {{ $t('request.fileLimit', { limit: format.fileSize(me!.attachment_max_bytes) }) }}</span>
    </span>
    <input :id="id" type="file" multiple class="sr-only" @change="pick">
  </label>
</template>
