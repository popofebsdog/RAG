<template>
  <div
    class="pipeline-node"
    :style="{
      borderColor: data.active ? data.color : '#D0CBC0',
      background: data.active ? data.color + '14' : '#F4F1EB',
      boxShadow: data.active ? `0 2px 12px ${data.color}30` : 'none',
    }"
  >
    <Handle type="target" :position="Position.Left" style="background: #A9A39A; width: 8px; height: 8px" />
    <div class="flex items-center gap-2">
      <span class="text-lg leading-none">{{ data.icon }}</span>
      <div>
        <div class="font-semibold text-[12px]" :style="{ color: data.active ? data.color : '#8A847C' }">
          {{ data.label }}
        </div>
        <div class="text-[11px] text-faint leading-tight mt-0.5 max-w-[120px] truncate">
          {{ data.sublabel }}
        </div>
      </div>
    </div>
    <Handle type="source" :position="Position.Right" style="background: #A9A39A; width: 8px; height: 8px" />
  </div>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

defineProps<{
  data: {
    label: string
    sublabel: string
    type: string
    color: string
    icon: string
    active: boolean
  }
}>()
</script>

<style scoped>
.pipeline-node {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1.5px solid;
  min-width: 140px;
  transition: all 0.25s ease;
}
.text-faint { color: #A9A39A; }
</style>
