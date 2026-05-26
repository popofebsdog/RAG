<template>
  <div class="min-h-screen bg-surface flex items-center justify-center p-6">
    <div class="w-full max-w-md space-y-8">

      <!-- Logo -->
      <div class="text-center space-y-2">
        <div class="text-5xl">🕸️</div>
        <h1 class="text-2xl font-bold text-white">Visual RAG System</h1>
        <p class="text-sm text-slate-500">建立研究專案，開始智慧文件分析</p>
      </div>

      <!-- Card -->
      <div class="rounded-2xl border border-white/10 bg-white/3 backdrop-blur p-8 space-y-6">
        <div>
          <h2 class="text-base font-semibold text-white mb-1">建立新專案</h2>
          <p class="text-xs text-slate-500">設定專案資訊後即可上傳文件、進行切分與語意搜尋</p>
        </div>

        <div class="space-y-4">
          <!-- Project name -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">專案名稱 *</label>
            <input
              v-model="name"
              placeholder="例：台南水災研究 2023"
              autofocus
              class="w-full px-3 py-2.5 rounded-xl bg-white/5 border text-sm text-white placeholder-slate-600 focus:outline-none transition-colors"
              :class="name.trim() ? 'border-indigo-500/50' : 'border-white/10 focus:border-white/25'"
              @keydown.enter="region || submit()"
            />
          </div>

          <!-- Region + Year -->
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <label class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">地區</label>
              <input
                v-model="region"
                placeholder="台南、高雄…"
                class="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 focus:border-white/25 text-sm text-white placeholder-slate-600 focus:outline-none transition-colors"
              />
            </div>
            <div class="space-y-1.5">
              <label class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">年份</label>
              <input
                v-model="yearStr"
                type="number"
                placeholder="2023"
                class="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 focus:border-white/25 text-sm text-white placeholder-slate-600 focus:outline-none transition-colors"
              />
            </div>
          </div>

          <!-- Perspective -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">研究視角</label>
            <input
              v-model="perspective"
              placeholder="水文分析、地質調查、社會影響…"
              class="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 focus:border-white/25 text-sm text-white placeholder-slate-600 focus:outline-none transition-colors"
              @keydown.enter="submit"
            />
          </div>
        </div>

        <!-- Submit -->
        <button
          class="w-full py-3 rounded-xl text-sm font-semibold transition-all"
          :class="name.trim()
            ? 'bg-indigo-500 hover:bg-indigo-400 text-white shadow-[0_0_20px_#6366f140]'
            : 'bg-white/5 text-slate-600 cursor-not-allowed'"
          :disabled="!name.trim()"
          @click="submit"
        >
          建立專案 →
        </button>
      </div>

      <p class="text-center text-xs text-slate-700">
        專案資訊存在本機，不會上傳任何資料
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { DocMetadata } from '../../types/rag'

const emit = defineEmits<{
  created: [name: string, meta: DocMetadata]
}>()

const name = ref('')
const region = ref('')
const yearStr = ref('')
const perspective = ref('')

function submit() {
  if (!name.value.trim()) return
  const y = parseInt(yearStr.value)
  emit('created', name.value.trim(), {
    region: region.value.trim() || undefined,
    year: isNaN(y) ? undefined : y,
    perspective: perspective.value.trim() || undefined,
  })
}
</script>
