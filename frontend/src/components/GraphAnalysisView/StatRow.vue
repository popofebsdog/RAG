<template>
  <div class="flex justify-between text-[12px]">
    <span style="color:#A9A39A">{{ label }}</span>
    <span class="font-mono" style="color:#2C2926">{{ value }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ label: string; value: string | number }>()
</script>
