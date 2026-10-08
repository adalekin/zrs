<script setup lang="ts">
// A value of a reference list as requests show it: a tag in the colour the finance director
// gave the value, plain text when the value has none. The name is always there to read.
defineProps<{ item: ReferenceItem }>()
</script>

<template>
  <span
    v-if="item.color"
    class="inline-flex h-6 max-w-full items-center rounded-md px-2 text-xs font-medium"
    :class="REFERENCE_FILLS[item.color]"
  >
    <span class="truncate">{{ item.name }}</span>
  </span>
  <span v-else>{{ item.name }}</span>
</template>
