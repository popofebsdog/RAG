<template>
  <button
    :title="tooltip"
    class="flex items-center gap-1 px-2 py-1 rounded text-xs border transition-colors"
    :class="
      active
        ? 'border-accent bg-accent/15 text-white'
        : 'border-border text-muted hover:border-slate-500 hover:text-slate-300'
    "
    @click="emit('click')"
  >
    <span>{{ icon }}</span>
    <span>{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
defineProps<{ active: boolean; label: string; icon: string; tooltip: string }>()
const emit = defineEmits<{ click: [] }>()
</script>
