<template>
  <div class="flex items-baseline gap-1">
    <span class="font-serif text-[15px] text-ink leading-none">{{ value }}</span>
    <span class="text-[10px] text-faint">{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ value: number; label: string }>()
</script>
