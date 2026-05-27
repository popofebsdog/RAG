<template>
  <div class="absolute inset-0 z-20 flex items-center justify-center bg-[#F4F1EB]/95 px-6 py-5">
    <section class="flex h-full w-full max-w-6xl flex-col overflow-hidden rounded-xl border bg-white shadow-xl" style="border-color:#D7DEE8">
      <header class="shrink-0 border-b px-5 py-4" style="border-color:#D7DEE8">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-[11px] font-semibold uppercase tracking-[0.12em]" style="color:#A9A39A">
              {{ lang === 'zh' ? '知識節點審核' : 'Knowledge node review' }}
            </p>
            <h2 class="mt-1 text-[18px] font-semibold" style="color:#172033">
              {{ preview.filename }}
            </h2>
            <p class="mt-1 text-[13px]" style="color:#667085">
              {{ lang === 'zh'
                ? '先確認或編輯 VLM/LLM 解析出的知識節點，核准後才會建立向量、節點關係與知識圖譜。'
                : 'Review extracted knowledge nodes before creating vectors, node relations, and the knowledge graph.' }}
            </p>
          </div>
          <div class="flex shrink-0 items-start gap-2">
            <div class="grid grid-cols-3 gap-2 text-center">
              <div class="stat-box">
                <b>{{ approvedNodes.length }}</b>
                <span>{{ lang === 'zh' ? '核准知識節點' : 'Approved' }}</span>
              </div>
              <div class="stat-box">
                <b>{{ approvedRelations.length }}</b>
                <span>{{ lang === 'zh' ? '預計節點關係' : 'Planned' }}</span>
              </div>
              <div class="stat-box">
                <b>{{ preview.total_pages }}</b>
                <span>{{ lang === 'zh' ? '頁' : 'Pages' }}</span>
              </div>
            </div>
            <button
              type="button"
              class="close-btn"
              :aria-label="lang === 'zh' ? '暫時收起審核' : 'Hide review'"
              @click="emit('close')"
            >
              x
            </button>
          </div>
        </div>
      </header>

      <div class="min-h-0 flex-1 overflow-hidden">
        <div class="h-full min-h-0 overflow-y-auto p-4">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="text-[12px] font-semibold" style="color:#41546F">
                {{ lang === 'zh' ? '候選知識節點' : 'Candidate knowledge nodes' }}
              </p>
              <p class="mt-1 text-[11px]" style="color:#667085">
                {{ lang === 'zh'
                  ? '節點關係會在確認後由系統建立；需要微調時，請到知識圖譜編輯操作。'
                  : 'Node relations will be built after confirmation; edit them in Knowledge Graph Edit.' }}
              </p>
            </div>
            <div class="flex shrink-0 gap-2">
              <button class="small-btn" type="button" @click="setAll(true)">
                {{ lang === 'zh' ? '全選' : 'All' }}
              </button>
              <button class="small-btn" type="button" @click="setAll(false)">
                {{ lang === 'zh' ? '全不選' : 'None' }}
              </button>
            </div>
          </div>

          <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <article
              v-for="node in draft.nodes"
              :key="node.id"
              class="rounded-lg border bg-[#F8FAFC] p-3"
              :style="{ borderColor: node.approved ? '#BFD0E3' : '#E4E7EC', opacity: node.approved ? 1 : 0.58 }"
            >
              <div class="mb-2 flex items-center gap-2">
                <label class="flex items-center gap-2 text-[12px] font-semibold" style="color:#172033">
                  <input v-model="node.approved" type="checkbox" class="h-4 w-4 accent-[#1E4E8C]" />
                  <span>{{ lang === 'zh' ? '知識節點' : 'Knowledge node' }}</span>
                </label>
                <span class="ml-auto text-[11px]" style="color:#667085">
                  {{ lang === 'zh' ? '原文頁' : 'Source p.' }}{{ node.source_page || '-' }}
                </span>
              </div>
              <input v-model="node.label" class="field mb-2 font-semibold" :placeholder="lang === 'zh' ? '知識節點標籤' : 'Knowledge node label'" />
              <textarea v-model="node.text" class="field min-h-[104px] resize-y leading-relaxed" :placeholder="lang === 'zh' ? '知識節點內容' : 'Knowledge node content'" />
            </article>
          </div>
        </div>
      </div>

      <footer class="shrink-0 border-t px-5 py-3 flex items-center justify-between" style="border-color:#D7DEE8">
        <button type="button" class="secondary-btn" :disabled="busy" @click="emit('discard')">
          {{ lang === 'zh' ? '取消這次解析' : 'Discard' }}
        </button>
        <button type="button" class="primary-btn" :disabled="busy || approvedNodes.length === 0" @click="confirm">
          {{ busy
            ? (lang === 'zh' ? '建立知識圖譜中…' : 'Building…')
            : (lang === 'zh' ? '確認並建立知識圖譜' : 'Confirm and Build Knowledge Graph') }}
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { IngestPreviewResponse } from '../../types/rag'

const props = defineProps<{
  preview: IngestPreviewResponse
  busy: boolean
  lang?: 'en' | 'zh'
}>()

const emit = defineEmits<{
  confirm: [preview: IngestPreviewResponse]
  discard: []
  close: []
}>()

const lang = computed(() => props.lang ?? 'zh')
const draft = reactive<IngestPreviewResponse>(clonePreview(props.preview))

watch(() => props.preview, (next) => {
  Object.assign(draft, clonePreview(next))
}, { deep: true })

const approvedNodes = computed(() => draft.nodes.filter((node) => node.approved && node.text.trim()))
const approvedRelations = computed(() => draft.relations.filter((relation) => relation.approved))

function clonePreview(preview: IngestPreviewResponse): IngestPreviewResponse {
  return JSON.parse(JSON.stringify(preview))
}

function setAll(approved: boolean): void {
  draft.nodes.forEach((node) => { node.approved = approved })
}

function confirm(): void {
  emit('confirm', clonePreview(draft))
}
</script>

<style scoped>
.stat-box {
  min-width: 78px;
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  padding: 8px 10px;
  background: #F8FAFC;
}
.stat-box b {
  display: block;
  color: #172033;
  font-size: 16px;
  line-height: 1;
}
.stat-box span {
  display: block;
  margin-top: 4px;
  color: #667085;
  font-size: 11px;
}
.field {
  width: 100%;
  border: 1px solid #D7DEE8;
  border-radius: 8px;
  background: #FFFFFF;
  color: #172033;
  font-size: 13px;
  padding: 8px 10px;
  outline: none;
}
.field:focus {
  border-color: #9BB7D4;
  box-shadow: 0 0 0 3px rgba(30, 78, 140, 0.08);
}
.small-btn,
.secondary-btn,
.primary-btn {
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  transition: opacity 0.15s ease, background 0.15s ease;
}
.small-btn {
  border: 1px solid #D7DEE8;
  background: #FFFFFF;
  color: #667085;
  padding: 5px 9px;
}
.secondary-btn {
  border: 1px solid #D7DEE8;
  background: #FFFFFF;
  color: #667085;
  padding: 9px 14px;
}
.primary-btn {
  background: #172033;
  color: #FFFFFF;
  padding: 10px 18px;
}
.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  color: #667085;
  font-size: 16px;
  line-height: 1;
  transition: background 0.15s ease, color 0.15s ease;
}
.close-btn:hover {
  background: #F1F5F9;
  color: #172033;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
