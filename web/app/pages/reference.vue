<script setup lang="ts">
import { XIcon } from '@lucide/vue'

const api = useApi()
const me = useMe()
const showFailure = useFailureToast()

// The page is for the finance director; the server refuses everybody else anyway.
const allowed = computed(() => me.value?.roles.includes('finance_director') === true)

const { data: items, reload } = useLoad(async () =>
  allowed.value ? await api<ReferenceItem[]>('/reference-items') : [],
)

const newNames = reactive<Record<ReferenceKind, string>>({ operation_type: '', payment_form: '', priority: '' })
const renaming = ref<{ id: number, name: string }>()

async function change(call: () => Promise<unknown>) {
  try {
    await call()
  }
  catch (error) {
    // A repeated name comes back as 409 with the message of the server.
    showFailure(error)
  }
  await reload()
}

function add(kind: ReferenceKind) {
  return change(async () => {
    await api('/reference-items', { method: 'POST', body: { kind, name: newNames[kind] } })
    newNames[kind] = ''
  })
}

function rename() {
  const { id, name } = renaming.value!
  return change(async () => {
    await api(`/reference-items/${id}`, { method: 'PATCH', body: { name } })
    renaming.value = undefined
  })
}

function setActive(item: ReferenceItem, isActive: boolean) {
  return change(() => api(`/reference-items/${item.id}`, { method: 'PATCH', body: { is_active: isActive } }))
}

// The value whose palette is open.
const coloring = ref<number>()

// The options of the palette: no colour first, then the colours.
const PALETTE = [null, ...REFERENCE_COLORS]

function setColor(item: ReferenceItem, color: ReferenceColor | null) {
  return change(async () => {
    await api(`/reference-items/${item.id}`, { method: 'PATCH', body: { color } })
    coloring.value = undefined
  })
}
</script>

<template>
  <div v-if="!allowed" class="grid gap-2">
    <h1 class="text-xl font-semibold">
      {{ $t('access.title') }}
    </h1>
    <p class="text-muted-foreground">
      {{ $t('access.financeDirectorOnly') }}
    </p>
  </div>

  <div v-else class="grid gap-8">
    <h1 class="text-xl font-semibold">
      {{ $t('reference.title') }}
    </h1>
    <p v-if="!items" class="text-muted-foreground text-sm">
      {{ $t('common.loading') }}
    </p>
    <!-- Three short lists side by side: each is seen whole, without scrolling past the others. -->
    <div v-else class="grid items-start gap-4 lg:grid-cols-3">
      <section v-for="kind in REFERENCE_KINDS" :key="kind" class="grid content-start gap-3 rounded-xl border p-4">
        <h2 class="font-semibold">
          {{ $t(`reference.${kind}`) }}
        </h2>
        <p v-if="!items.some(item => item.kind === kind)" class="text-muted-foreground text-sm">
          {{ $t('reference.empty') }}
        </p>
        <ul class="grid gap-2">
          <li
            v-for="item in items.filter(item => item.kind === kind)"
            :key="item.id"
            class="flex flex-wrap items-center gap-x-3 gap-y-2"
          >
            <button
              type="button"
              class="ring-offset-background ring-border size-5 shrink-0 rounded-full ring-offset-2 transition-shadow hover:ring-2"
              :class="item.color ? REFERENCE_SWATCHES[item.color] : 'border-muted-foreground/50 border border-dashed'"
              :aria-label="$t('reference.color', { name: item.name })"
              :aria-expanded="coloring === item.id"
              @click="coloring = coloring === item.id ? undefined : item.id"
            />
            <form
              v-if="renaming?.id === item.id"
              class="flex flex-1 items-center gap-2"
              novalidate
              @submit.prevent="rename"
            >
              <Input v-model="renaming.name" :aria-label="$t('reference.name')" />
              <Button type="submit" size="sm">
                {{ $t('reference.save') }}
              </Button>
              <Button type="button" variant="outline" size="sm" @click="renaming = undefined">
                {{ $t('reference.dismiss') }}
              </Button>
            </form>
            <template v-else>
              <span class="flex-1" :class="{ 'text-muted-foreground line-through': !item.is_active }">{{ item.name }}</span>
              <Button variant="ghost" size="sm" @click="renaming = { id: item.id, name: item.name }">
                {{ $t('reference.rename') }}
              </Button>
            </template>
            <Switch
              :model-value="item.is_active"
              :aria-label="$t('reference.active')"
              @update:model-value="value => setActive(item, value)"
            />
            <!-- The palette opens under the name of the value it colours: one row of circles, the chosen one is ringed. -->
            <div
              v-if="coloring === item.id"
              class="flex w-full flex-wrap gap-2 pl-8"
              role="radiogroup"
              :aria-label="$t('reference.color', { name: item.name })"
            >
              <button
                v-for="color in PALETTE"
                :key="color ?? 'none'"
                type="button"
                role="radio"
                class="ring-offset-background flex size-6 items-center justify-center rounded-full ring-offset-2 transition-shadow hover:ring-2"
                :class="[
                  color ? REFERENCE_SWATCHES[color] : 'text-muted-foreground border-muted-foreground/50 border border-dashed',
                  item.color === color ? 'ring-foreground/70 ring-2' : 'ring-border',
                ]"
                :aria-checked="item.color === color"
                :aria-label="color ? $t(`color.${color}`) : $t('reference.noColor')"
                :title="color ? $t(`color.${color}`) : $t('reference.noColor')"
                @click="setColor(item, color)"
              >
                <XIcon v-if="!color" class="size-3.5" />
              </button>
            </div>
          </li>
        </ul>
        <form class="flex items-center gap-2" novalidate @submit.prevent="add(kind)">
          <Input v-model="newNames[kind]" :placeholder="$t('reference.name')" :aria-label="$t('reference.name')" />
          <Button type="submit" variant="outline">
            {{ $t('reference.add') }}
          </Button>
        </form>
      </section>
    </div>
  </div>
</template>
