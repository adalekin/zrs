<script setup lang="ts">
// The choice of a person among the given ones: the moderator or the payer of a request.
// The people come from the owner of the screen; the choice goes back as the id in a string,
// empty when nobody is chosen.
defineProps<{
  people: Person[]
  /** What the empty choice is called. Without it somebody has to be chosen. */
  emptyLabel?: string
}>()

const chosen = defineModel<string>({ required: true })
</script>

<template>
  <NativeSelect v-model="chosen" class="w-full">
    <NativeSelectOption v-if="emptyLabel !== undefined" value="">
      {{ emptyLabel }}
    </NativeSelectOption>
    <NativeSelectOption v-for="person in people" :key="person.id" :value="String(person.id)">
      {{ person.name }}
    </NativeSelectOption>
  </NativeSelect>
</template>
