<template>
  <div>
    <!-- Project list -->
    <div class="space-y-1.5">
      <div
        v-if="projects.length === 0 && !showCreate"
        class="empty-box"
      >
        <p class="text-[12px] mb-1.5" style="color:#667085">{{ lang === 'zh' ? '尚無專案' : 'No projects yet' }}</p>
        <button
          class="text-[12px] font-semibold transition-colors"
          style="color:#1E4E8C"
          @click="showCreate = true"
        >{{ lang === 'zh' ? '建立第一個專案 →' : 'Create first project →' }}</button>
      </div>

      <div
        v-for="p in projects"
        :key="p.id"
        class="project-row group"
        :class="activeProjectId === p.id
          ? 'is-active'
          : 'hover:bg-[#F1F6FB]'"
        @click="p.id !== activeProjectId && emit('switch', p.id)"
      >
        <!-- Status dot -->
        <div
          class="w-2 h-2 rounded-full shrink-0"
          :style="{ background: activeProjectId === p.id ? '#1E4E8C' : '#A9B4C2' }"
        />

        <!-- Info -->
        <div class="min-w-0 flex-1">
          <p
            class="text-[13px] font-semibold truncate leading-tight text-left"
            :style="{ color: activeProjectId === p.id ? '#172033' : '#41546F' }"
          >{{ p.name }}</p>
          <p class="text-[11px] truncate leading-tight mt-0.5 text-left" style="color:#667085">
            <span v-if="p.meta.region">{{ p.meta.region }}</span>
            <span v-if="p.meta.date"> · {{ p.meta.date }}</span>
            <span v-else-if="p.meta.year"> · {{ p.meta.year }}</span>
            <span v-if="!p.meta.region && !p.meta.date && !p.meta.year">{{ lang === 'zh' ? '無描述' : 'No metadata' }}</span>
          </p>
        </div>

        <!-- Delete button (hover, not active) -->
        <button
          v-if="activeProjectId !== p.id"
          class="shrink-0 opacity-0 group-hover:opacity-100 text-xs transition-all delete-button"
          @click.stop="emit('delete', p.id)"
        >✕</button>
      </div>
    </div>

    <!-- New project button -->
    <button
      v-if="!showCreate"
      class="w-full mt-2 flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-[12px] font-semibold border border-dashed transition-all"
      style="border-color:#D7DEE8;color:#667085;background:#FFFFFF"
      @click="showCreate = true"
    >
      <span class="text-sm leading-none">+</span>
      {{ lang === 'zh' ? '新增專案' : 'New project' }}
    </button>

    <!-- Create form -->
    <Transition name="slide">
      <form v-if="showCreate" class="mt-2 rounded-lg border p-2.5 space-y-2" style="border-color:#D7DEE8;background:#FFFFFF" @submit.prevent="submitCreate">
        <input
          ref="nameInput"
          v-model="newName"
          :placeholder="lang === 'zh' ? '專案名稱 *' : 'Project name *'"
          class="form-input"
          @keydown.esc="showCreate = false"
        />
        <div class="grid grid-cols-2 gap-1.5">
          <select
            v-model="newRegion"
            class="form-input text-[11px]"
          >
            <option value="">{{ lang === 'zh' ? '地點篩選' : 'Location' }}</option>
            <option v-for="option in locationOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <select
            v-model="newDate"
            class="form-input text-[11px]"
          >
            <option value="">{{ lang === 'zh' ? '日期篩選' : 'Date' }}</option>
            <option v-for="option in dateOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
        <div
          v-if="newRegion || newDate"
          class="external-preview"
          :class="externalPreview?.available ? 'is-ready' : 'is-muted'"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="text-[11px] font-semibold">
              {{ lang === 'zh' ? 'DSM 影像辨識資料' : 'DSM vision data' }}
            </span>
            <span v-if="externalPreviewLoading" class="text-[10px]" style="color:#667085">
              {{ lang === 'zh' ? '檢查中…' : 'Checking…' }}
            </span>
            <span v-else class="text-[10px]" style="color:#667085">
              {{ externalPreview?.records.length ?? 0 }} {{ lang === 'zh' ? '筆' : 'records' }}
            </span>
          </div>
          <p class="mt-1 line-clamp-2 text-[11px]" style="color:#667085">
            {{ externalPreviewMessage }}
          </p>
        </div>
        <div class="flex gap-1.5">
          <button
            type="submit"
            class="flex-1 py-1.5 rounded-lg text-[11px] font-semibold transition-all"
            :style="newName.trim()
              ? { background: '#172033', color: '#FFFFFF' }
              : { background: '#EEF3F8', color: '#A9B4C2', cursor: 'not-allowed' }"
            :disabled="!newName.trim()"
          >{{ lang === 'zh' ? '建立' : 'Create' }}</button>
          <button
            type="button"
            class="px-3 py-1.5 rounded-lg text-[11px] border transition-all"
            style="border-color:#D7DEE8;color:#667085;background:#FFFFFF"
            @click="showCreate = false"
          >{{ lang === 'zh' ? '取消' : 'Cancel' }}</button>
        </div>
      </form>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import type { Project, DocMetadata, ProjectFilterOptions, ProjectOption, ExternalVisionPreviewResponse } from '../../types/rag'

const props = defineProps<{
  projects: Project[]
  activeProjectId: string | null
  filterOptions?: ProjectFilterOptions
  previewExternalVision?: (location?: string, date?: string) => Promise<ExternalVisionPreviewResponse>
  lang?: 'en' | 'zh'
}>()

const emit = defineEmits<{
  create: [name: string, meta: DocMetadata]
  switch: [id: string]
  delete: [id: string]
}>()

const lang = computed(() => props.lang ?? 'zh')

const showCreate = ref(false)
const nameInput = ref<HTMLInputElement | null>(null)

const newName = ref('')
const newRegion = ref('')
const newDate = ref('')
const externalPreview = ref<ExternalVisionPreviewResponse | null>(null)
const externalPreviewLoading = ref(false)
let previewSeq = 0

const fallbackLocations: ProjectOption[] = [
  { value: '台2線70.1K 平浪橋南側', label: '台2線70.1K 平浪橋南側' },
  { value: '龍門', label: '龍門' },
]
const fallbackDates: ProjectOption[] = [
  { value: '2024-06-03', label: '2024-06-03 崩塌發生' },
  { value: '2024-06-06', label: '2024-06-06 報告日期' },
]

const locationOptions = computed(() => props.filterOptions?.locations?.length ? props.filterOptions.locations : fallbackLocations)
const dateOptions = computed(() => props.filterOptions?.dates?.length ? props.filterOptions.dates : fallbackDates)
const externalPreviewMessage = computed(() => {
  if (externalPreviewLoading.value) return lang.value === 'zh' ? '正在讀取 DSM API 狀態。' : 'Reading DSM API status.'
  if (!externalPreview.value) return lang.value === 'zh' ? '建立專案後會嘗試匯入外部辨識 JSON 作為知識節點。' : 'External JSON will be imported as knowledge nodes after project creation.'
  return externalPreview.value.message || (externalPreview.value.available
    ? (lang.value === 'zh' ? '建立專案後會匯入這些外部知識節點。' : 'These external knowledge nodes will be imported after project creation.')
    : (lang.value === 'zh' ? '目前沒有可匯入的 DSM JSON。' : 'No DSM JSON is available yet.'))
})

watch(showCreate, async (v) => {
  if (v) {
    await nextTick()
    nameInput.value?.focus()
  }
})

watch([newRegion, newDate], async ([region, date]) => {
  externalPreview.value = null
  if (!props.previewExternalVision || (!region && !date)) return
  const seq = ++previewSeq
  externalPreviewLoading.value = true
  try {
    const result = await props.previewExternalVision(region || undefined, date || undefined)
    if (seq === previewSeq) externalPreview.value = result
  } catch (error) {
    if (seq === previewSeq) {
      externalPreview.value = {
        available: false,
        message: lang.value === 'zh' ? 'DSM API 尚未連線或沒有對應資料。' : 'DSM API is unavailable or has no matching data.',
        records: [],
      }
    }
  } finally {
    if (seq === previewSeq) externalPreviewLoading.value = false
  }
})

function submitCreate() {
  if (!newName.value.trim()) return
  const yearText = newDate.value.match(/^\d{4}/)?.[0]
  const year = yearText ? parseInt(yearText, 10) : undefined
  emit('create', newName.value.trim(), {
    region: newRegion.value || undefined,
    date: newDate.value || undefined,
    year,
  })
  newName.value = ''
  newRegion.value = ''
  newDate.value = ''
  externalPreview.value = null
  showCreate.value = false
}
</script>

<style scoped>
.project-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.project-row.is-active {
  border-color: #D7DEE8;
  background: #FFFFFF;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  cursor: default;
}
.delete-button {
  color: #A9B4C2;
}
.delete-button:hover {
  color: #B91C1C;
}
.empty-box {
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  background: #FFFFFF;
  padding: 12px;
}
.form-input {
  width: 100%;
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  background: #F8FAFC;
  color: #172033;
  font-size: 12px;
  padding: 7px 10px;
  outline: none;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.form-input:focus {
  border-color: #9BB7D4;
  background: #FFFFFF;
}
.external-preview {
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  padding: 8px 9px;
  background: #F8FAFC;
}
.external-preview.is-ready {
  border-color: #9CC7CF;
  background: #F1FAFB;
}
.external-preview.is-muted {
  border-color: #E2E8F0;
  background: #F8FAFC;
}
.slide-enter-active, .slide-leave-active {
  transition: all 0.15s ease;
  overflow: hidden;
}
.slide-enter-from, .slide-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
}
.slide-enter-to, .slide-leave-from {
  opacity: 1;
  max-height: 300px;
}
</style>
