<template>
  <div class="w-full h-full flex overflow-hidden" style="background:#F8FAFC">
    <aside class="w-[340px] shrink-0 border-r overflow-hidden flex flex-col" style="border-color:#D7DEE8;background:#F8FAFC">
      <div class="h-[58px] shrink-0 border-b px-4 flex items-center justify-between" style="border-color:#D7DEE8">
        <div>
          <p class="text-[14px] font-semibold" style="color:#172033">{{ lang === 'zh' ? 'Graph JSON API' : 'Graph JSON API' }}</p>
          <p class="text-[12px]" style="color:#667085">{{ lang === 'zh' ? '目前專案輸出的圖譜檔案' : 'Exported graph files for this project' }}</p>
        </div>
        <button class="icon-button" :disabled="loading" @click="loadList">
          <span :class="loading ? 'animate-spin inline-block' : ''">↻</span>
        </button>
      </div>

      <div class="p-3 border-b space-y-2" style="border-color:#D7DEE8">
        <div class="endpoint-card">
          <div class="method-get">GET</div>
          <div class="min-w-0">
            <p class="endpoint-path">/graphs/json</p>
            <p class="endpoint-desc">{{ lang === 'zh' ? '列出 project_id 的所有 graph JSON' : 'List graph JSON by project_id' }}</p>
          </div>
        </div>
        <div class="endpoint-card">
          <div class="method-get">GET</div>
          <div class="min-w-0">
            <p class="endpoint-path">/graphs/json/{filename}</p>
            <p class="endpoint-desc">{{ lang === 'zh' ? '讀取單一 JSON 內容' : 'Read a graph JSON file' }}</p>
          </div>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-3 space-y-2">
        <div v-if="!projectId" class="empty-box">{{ lang === 'zh' ? '尚未選擇專案' : 'No project selected' }}</div>
        <div v-else-if="loading" class="empty-box">{{ lang === 'zh' ? '讀取中' : 'Loading' }}</div>
        <div v-else-if="files.length === 0" class="empty-box">
          {{ lang === 'zh' ? '目前沒有 graph JSON。重新整理圖分析、知識圖譜或詢問一次後會產生。' : 'No graph JSON yet. Refresh graph views or ask a question to generate files.' }}
        </div>
        <button
          v-for="file in files"
          :key="file.filename"
          class="file-row"
          :class="{ active: selected?.filename === file.filename }"
          @click="selectFile(file)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="text-[13px] font-semibold truncate" style="color:#172033">{{ titleFor(file.graph_name) }}</p>
              <p class="text-[11px] truncate" style="color:#667085">{{ file.filename }}</p>
            </div>
            <span class="json-chip">JSON</span>
          </div>
          <div class="mt-2 grid grid-cols-3 gap-1.5 text-[11px]">
            <Metric label="Nodes" :value="file.node_count" />
            <Metric label="Edges" :value="file.edge_count" />
            <Metric label="KB" :value="formatKb(file.size_bytes)" />
          </div>
        </button>
      </div>
    </aside>

    <main class="flex-1 min-w-0 flex flex-col">
      <div class="h-[58px] shrink-0" aria-hidden="true" />

      <div class="flex-1 overflow-auto px-4 pb-4">
        <div v-if="error" class="notice-box">{{ error }}</div>
        <div v-else-if="jsonText" class="json-shell">
          <div class="json-actions">
            <button class="secondary-button" :disabled="!jsonText" @click="copyJson">{{ copied ? (lang === 'zh' ? '已複製' : 'Copied') : (lang === 'zh' ? '複製' : 'Copy') }}</button>
            <a v-if="selected && projectId" class="secondary-button" :href="apiFileUrl(selected.filename)" target="_blank" rel="noreferrer">
              {{ lang === 'zh' ? '開啟 API' : 'Open API' }}
            </a>
          </div>
          <pre class="json-preview">{{ jsonText }}</pre>
        </div>
        <div v-else class="empty-preview">
          <p>{{ lang === 'zh' ? '左側選檔後會顯示完整 JSON。' : 'Select a file to inspect its JSON.' }}</p>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import type { GraphJsonInfo, GraphJsonListResponse } from '../../types/rag'

const BASE = '/api'

const Metric = {
  props: ['label', 'value'],
  render(this: { label: string; value: string | number }) {
    return h('div', { class: 'rounded-md border px-2 py-1', style: 'border-color:#D7DEE8;background:#FFFFFF' }, [
      h('p', { class: 'text-[10px]', style: 'color:#667085' }, this.label),
      h('p', { class: 'text-[12px] font-semibold tabular-nums', style: 'color:#172033' }, String(this.value)),
    ])
  },
}

const props = defineProps<{
  projectId: string | null
  lang: 'en' | 'zh'
  active: boolean
}>()

const files = ref<GraphJsonInfo[]>([])
const selected = ref<GraphJsonInfo | null>(null)
const jsonData = ref<unknown>(null)
const loading = ref(false)
const error = ref('')
const copied = ref(false)

const jsonText = computed(() => jsonData.value ? JSON.stringify(jsonData.value, null, 2) : '')
watch(() => props.projectId, () => {
  files.value = []
  selected.value = null
  jsonData.value = null
  if (props.projectId) loadList()
})

watch(() => props.active, (active) => {
  if (active) loadList()
})

onMounted(() => {
  if (props.projectId) loadList()
})

function apiFileUrl(filename: string) {
  const params = new URLSearchParams({ project_id: props.projectId ?? 'default' })
  return `${BASE}/graphs/json/${encodeURIComponent(filename)}?${params.toString()}`
}

async function loadList() {
  if (!props.projectId) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get<GraphJsonListResponse>(`${BASE}/graphs/json`, {
      params: { project_id: props.projectId },
    })
    files.value = data.files
    if (selected.value && !files.value.some((file) => file.filename === selected.value?.filename)) {
      selected.value = null
      jsonData.value = null
    }
  } catch (e: unknown) {
    error.value = axios.isAxiosError(e) ? (e.response?.data?.detail ?? e.message) : 'Load failed'
  } finally {
    loading.value = false
  }
}

async function selectFile(file: GraphJsonInfo) {
  selected.value = file
  error.value = ''
  try {
    const { data } = await axios.get(apiFileUrl(file.filename))
    jsonData.value = data
  } catch (e: unknown) {
    jsonData.value = null
    error.value = axios.isAxiosError(e) ? (e.response?.data?.detail ?? e.message) : 'Load failed'
  }
}

async function copyJson() {
  if (!jsonText.value) return
  await navigator.clipboard.writeText(jsonText.value)
  copied.value = true
  window.setTimeout(() => { copied.value = false }, 1200)
}

function titleFor(name: string) {
  const zh: Record<string, string> = {
    graph_analysis: '圖分析與編輯',
    knowledge_graph: '知識圖譜',
    query_graph: '詢問流程圖',
    embedding_space: 'Embedding 空間',
  }
  const en: Record<string, string> = {
    graph_analysis: 'Graph Analysis',
    knowledge_graph: 'Knowledge Graph',
    query_graph: 'Query Graph',
    embedding_space: 'Embedding Space',
  }
  return props.lang === 'zh' ? (zh[name] ?? name) : (en[name] ?? name)
}

function formatKb(bytes: number) {
  return Math.max(1, Math.round(bytes / 1024))
}
</script>

<style scoped>
.endpoint-card,
.file-row {
  width: 100%;
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  background: #FFFFFF;
  padding: 10px;
  text-align: left;
}
.endpoint-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: start;
}
.file-row {
  transition: border-color 0.15s ease, background 0.15s ease;
}
.file-row:hover,
.file-row.active {
  border-color: #9BB7D4;
  background: #F1F6FB;
}
.method-get {
  border-radius: 5px;
  background: #E8F3EE;
  color: #17643A;
  font-size: 11px;
  font-weight: 800;
  padding: 3px 6px;
}
.endpoint-path {
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #172033;
}
.endpoint-desc {
  margin-top: 2px;
  font-size: 11px;
  color: #667085;
}
.json-chip {
  border-radius: 5px;
  border: 1px solid #D7DEE8;
  background: #F8FAFC;
  color: #667085;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
}
.icon-button,
.secondary-button {
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  background: #FFFFFF;
  color: #41546F;
  font-size: 12px;
  font-weight: 600;
  padding: 7px 10px;
}
.icon-button {
  width: 32px;
  height: 32px;
  padding: 0;
}
.secondary-button:disabled,
.icon-button:disabled {
  opacity: 0.45;
}
.empty-box,
.notice-box,
.empty-preview {
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  background: #FFFFFF;
  color: #667085;
  font-size: 13px;
  line-height: 1.6;
  padding: 14px;
}
.notice-box {
  border-color: #FECACA;
  color: #B91C1C;
  background: #FEF2F2;
}
.empty-preview {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.json-shell {
  position: relative;
  min-height: 100%;
}
.json-actions {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 0 0 8px;
  background: #F8FAFC;
}
.json-preview {
  min-height: calc(100vh - 150px);
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  background: #111827;
  color: #E5E7EB;
  font-size: 12px;
  line-height: 1.55;
  padding: 16px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
