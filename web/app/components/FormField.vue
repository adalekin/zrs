<script setup lang="ts">
defineProps<{
  id: string
  label: string
  required?: boolean
  hint?: string
  /** A caution about the value that does not stop the form. */
  warning?: string
  /** Message of the server for this field. */
  error?: string
}>()
</script>

<template>
  <div class="grid content-start gap-1.5">
    <Label :for="id" class="gap-0.5">
      {{ label }}
      <span v-if="required" class="text-destructive" aria-hidden="true">*</span>
    </Label>
    <slot />
    <p v-if="hint" class="text-muted-foreground text-xs">
      {{ hint }}
    </p>
    <p v-if="warning" class="text-xs text-amber-700" role="status">
      {{ warning }}
    </p>
    <p v-if="error" class="text-destructive text-xs" role="alert">
      {{ error }}
    </p>
  </div>
</template>
