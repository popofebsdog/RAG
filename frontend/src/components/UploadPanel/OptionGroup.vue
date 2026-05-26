<template>
  <div>
    <p class="text-[10px] font-semibold uppercase tracking-[0.08em] text-faint mb-1.5">{{ label }}</p>
    <div class="grid grid-cols-2 gap-1">
      <button
        v-for="opt in options"
        :key="opt.value"
        :title="opt.desc"
        class="relative flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-left transition-all duration-150"
        :class="
          modelValue === opt.value
            ? 'border-ink/25 bg-black/[0.06]'
            : 'border-border hover:border-ink/15 hover:bg-black/[0.02]'"
        @click="emit('update:modelValue', opt.value)"
      >
        <span class="text-xs leading-none">{{ opt.icon }}</span>
        <span
          class="text-[11px] font-medium truncate"
          :class="modelValue === opt.value ? 'text-ink' : 'text-sub'"
        >{{ opt.label }}</span>
        <span
          v-if="modelValue === opt.value"
          class="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-ink/50"
        />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  options: { value: string; label: string; icon: string; desc: string }[]
  modelValue: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
