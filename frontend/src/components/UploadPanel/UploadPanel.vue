<template>
  <div class="space-y-3">
    <!-- Drop zone -->
    <div
      class="relative rounded-lg border border-dashed transition-all duration-200 cursor-pointer"
      :class="
        isDragging
          ? 'is-dragging'
          : ingestResult
            ? 'is-done'
            : 'is-idle'"
      @click="fileInput?.click()"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="onDrop"
    >
      <input ref="fileInput" type="file" accept=".pdf" class="hidden" @change="onFileChange" />

      <!-- Idle -->
      <div v-if="!ingesting && !ingestResult" class="py-5 flex flex-col items-center gap-2">
        <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background:#EEF3F8;border:1px solid #D7DEE8">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#A9A39A" stroke-width="1.5" stroke-linecap="round">
            <path d="M4 2h6l3 3v9H4zM9 2v3h3M6 8h5M6 10.5h3"/>
          </svg>
        </div>
        <p class="text-[12px]" style="color:#41546F">Drop PDF or <span style="color:#1E4E8C;text-decoration:underline;text-underline-offset:2px">browse</span></p>
        <p class="text-[11px]" style="color:#667085">{{ lang === 'zh' ? '抽取關鍵段落、建立關係與向量索引' : 'Extract key passages, relations, and vectors' }}</p>
      </div>

      <!-- Processing -->
      <div v-else-if="ingesting" class="py-5 flex flex-col items-center gap-2.5">
        <div class="w-7 h-7 rounded-full border-2 animate-spin" style="border-color:#D7DEE8;border-top-color:#172033" />
        <p class="text-[12px]" style="color:#41546F">
          {{ lang === 'zh' ? '建立初始知識圖譜中…' : 'Building initial knowledge graph…' }}
        </p>
      </div>

      <!-- Done -->
      <div v-else-if="ingestResult" class="py-3 px-3">
        <div class="flex items-start gap-2.5">
          <div class="w-7 h-7 rounded-lg flex items-center justify-center text-xs shrink-0 mt-0.5"
            :style="ingestResult.total_chunks > 0
              ? { background: '#E8F3EE', border: '1px solid #BAD7C3', color: '#17643A' }
              : { background: '#EEF3F8', border: '1px solid #D7DEE8', color: '#41546F' }"
          >{{ ingestResult.total_chunks > 0 ? '✓' : '📖' }}</div>
          <div class="min-w-0">
            <p class="text-[12px] font-semibold truncate" style="color:#172033">{{ ingestResult.filename }}</p>
            <div class="flex gap-3 mt-0.5">
              <span class="text-[11px]" style="color:#667085"><span class="font-semibold" style="color:#41546F">{{ ingestResult.total_pages }}</span> pages</span>
              <span class="text-[11px]" style="color:#667085"><span class="font-semibold" style="color:#41546F">{{ ingestResult.total_chunks }}</span> chunks</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add or update PDF -->
    <button
      v-if="ingestResult && !ingesting"
      class="w-full py-2 rounded-lg text-[12px] font-semibold border border-dashed transition-all flex items-center justify-center gap-1.5"
      style="border-color:#D7DEE8;color:#667085;background:#FFFFFF"
      @click="fileInput?.click()"
    >
      <span class="text-sm leading-none">+</span>
      {{ lang === 'zh' ? '加入或更新 PDF' : 'Add or update PDF' }}
    </button>

    <!-- Error -->
    <div v-if="error" class="rounded-lg border px-3 py-2" style="background:#FEF2F2;border-color:#FECACA">
      <p class="text-[11px]" style="color:#B91C1C">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { IngestResponse } from '../../types/rag'

const props = defineProps<{
  ingesting: boolean
  ingestResult: IngestResponse | null
  error: string | null
  lang?: 'en' | 'zh'
}>()

const lang = computed(() => props.lang ?? 'zh')

const emit = defineEmits<{
  upload: [file: File, loaderType: string, strategy: 'auto' | 'manual']
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const isDragging = ref(false)
const loaderType = ref('vlm')

function handleFile(file: File) {
  if (file.type !== 'application/pdf') return
  emit('upload', file, loaderType.value, 'auto')
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) handleFile(input.files[0])
  input.value = ''
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) handleFile(file)
}
</script>

<style scoped>
.is-idle {
  border-color: #D7DEE8;
  background: #FFFFFF;
}
.is-idle:hover {
  border-color: #9BB7D4;
  background: #F8FAFC;
}
.is-dragging {
  border-color: #1E4E8C;
  background: #F1F6FB;
}
.is-done {
  border-color: #BAD7C3;
  background: #F8FCFA;
}
</style>
