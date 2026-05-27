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
              @keydown.enter="submit()"
            />
          </div>

          <!-- Location + Date -->
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <label class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">地點</label>
              <select
                v-model="region"
                class="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 focus:border-white/25 text-sm text-white placeholder-slate-600 focus:outline-none transition-colors"
              >
                <option value="">選擇地點</option>
                <option v-for="option in locationOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>
            <div class="space-y-1.5">
              <label class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">日期</label>
              <select
                v-model="date"
                class="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 focus:border-white/25 text-sm text-white placeholder-slate-600 focus:outline-none transition-colors"
              >
                <option value="">選擇日期</option>
                <option v-for="option in dateOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>
          </div>

          <!-- Perspective -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">研究視角</label>
            <select
              v-model="perspective"
              class="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 focus:border-white/25 text-sm text-white placeholder-slate-600 focus:outline-none transition-colors"
              @keydown.enter="submit"
            >
              <option value="">選擇視角</option>
              <option v-for="option in perspectiveOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
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
        專案資訊會保存為後續知識圖譜與外部資料知識節點的篩選條件
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DocMetadata, ProjectFilterOptions, ProjectOption } from '../../types/rag'

const props = defineProps<{
  filterOptions?: ProjectFilterOptions
}>()

const emit = defineEmits<{
  created: [name: string, meta: DocMetadata]
}>()

const name = ref('')
const region = ref('')
const date = ref('')
const perspective = ref('')

const fallbackLocations: ProjectOption[] = [
  { value: '台2線70.1K 平浪橋南側', label: '台2線70.1K 平浪橋南側' },
  { value: '龍門', label: '龍門' },
]
const fallbackDates: ProjectOption[] = [
  { value: '2024-06-03', label: '2024-06-03 崩塌發生' },
  { value: '2024-06-06', label: '2024-06-06 報告日期' },
]
const fallbackPerspectives: ProjectOption[] = [
  { value: '地質調查', label: '地質調查' },
  { value: '水文雨量', label: '水文雨量' },
  { value: '道路災害', label: '道路災害' },
]

const locationOptions = computed(() => props.filterOptions?.locations?.length ? props.filterOptions.locations : fallbackLocations)
const dateOptions = computed(() => props.filterOptions?.dates?.length ? props.filterOptions.dates : fallbackDates)
const perspectiveOptions = computed(() => props.filterOptions?.perspectives?.length ? props.filterOptions.perspectives : fallbackPerspectives)

function submit() {
  if (!name.value.trim()) return
  const yearText = date.value.match(/^\d{4}/)?.[0]
  const year = yearText ? parseInt(yearText, 10) : undefined
  emit('created', name.value.trim(), {
    region: region.value || undefined,
    date: date.value || undefined,
    year,
    perspective: perspective.value || undefined,
  })
}
</script>
