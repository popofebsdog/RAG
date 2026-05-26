<template>
  <Teleport to="body">
    <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="emit('close')" />

      <div class="relative w-[94vw] h-[90vh] bg-canvas border border-border rounded-2xl flex overflow-hidden shadow-2xl">
        <aside class="w-60 border-r border-border flex flex-col shrink-0 bg-rail">
          <div class="px-4 py-3 border-b border-border">
            <p class="text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">Documents</p>
          </div>

          <div class="flex-1 overflow-y-auto p-2 space-y-0.5 min-h-0">
            <button
              v-for="doc in docs"
              :key="doc.filename"
              class="w-full text-left px-3 py-2 rounded-lg transition-all"
              :class="selectedDoc === doc.filename
                ? 'bg-surface border border-border shadow-sm'
                : 'border border-transparent hover:bg-black/[0.04]'"
              @click="selectDoc(doc.filename)"
            >
              <p class="text-[12px] truncate" :class="selectedDoc === doc.filename ? 'text-ink font-medium' : 'text-sub'">
                {{ doc.filename }}
              </p>
              <p class="text-[10px] mt-0.5 text-faint">
                {{ doc.chunk_count > 0 ? `${doc.chunk_count} chunks` : '待解析' }}
              </p>
            </button>
            <p v-if="docs.length === 0" class="text-[11px] text-faint px-3 py-2">尚未上傳文件</p>
          </div>

          <div v-if="docManualChunks.length > 0" class="border-t border-border p-2 shrink-0">
            <div class="flex items-center gap-1 px-1 py-1 mb-1">
              <p class="flex-1 text-[10px] font-semibold py-0.5 rounded text-amber-700 bg-amber-50 text-center">
                圖譜節點 {{ docManualChunks.length }}
              </p>
            </div>

            <div class="space-y-0.5 max-h-56 overflow-y-auto">
              <button
                v-for="mc in docManualChunks"
                :key="mc.chunk_id"
                class="w-full text-left px-2 py-1.5 rounded-lg border transition-all"
                :class="focusedChunkId === mc.chunk_id
                  ? 'border-amber-500 bg-amber-100 shadow-sm'
                  : 'border-amber-200 bg-amber-50/60 hover:border-amber-400 hover:bg-amber-50'"
                @click="goToChunkSource(mc)"
              >
                <div class="flex items-center gap-2">
                  <p class="min-w-0 flex-1 text-[11px] text-amber-800 font-medium truncate">{{ mc.label }}</p>
                  <span v-if="chunkPage(mc)" class="shrink-0 text-[9px] font-mono text-amber-700 bg-white/70 border border-amber-200 rounded px-1">
                    p.{{ chunkPage(mc) }}
                  </span>
                </div>
                <p class="text-[10px] text-faint line-clamp-2">{{ mc.text }}</p>
              </button>
            </div>
          </div>
        </aside>

        <main class="flex-1 flex flex-col overflow-hidden bg-canvas">
          <div class="px-6 py-3 border-b border-border flex items-center justify-between shrink-0">
            <div>
              <h3 class="text-[14px] font-medium text-ink">{{ selectedDoc || '從左側選擇文件' }}</h3>
              <p class="text-[11px] text-faint mt-0.5">PDF 原檔畫面；在頁面上拖曳框選，VLM 讀圖後可確認建立 chunk。</p>
            </div>
            <div class="flex items-center gap-3">
              <Transition name="fade">
                <div v-if="successMsg" class="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-[11px] text-amber-700">
                  {{ successMsg }}
                </div>
              </Transition>
              <div v-if="loading || selectionAnalyzing" class="w-4 h-4 rounded-full border-2 border-border border-t-ink animate-spin" />
              <button class="text-faint hover:text-ink text-xl leading-none transition-colors" @click="emit('close')">×</button>
            </div>
          </div>

          <div
            ref="readerEl"
            class="reader-body flex-1 min-h-0 overflow-y-auto bg-[#E9E5DC] px-6 py-6"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointercancel="cancelDrag"
          >
            <div v-if="!selectedDoc" class="flex items-center justify-center h-full text-faint text-[13px]">
              從左側選擇文件開始閱讀
            </div>

            <div v-else-if="loading && !pdfAvailable" class="flex items-center justify-center h-full gap-3">
              <div class="w-5 h-5 rounded-full border-2 border-border border-t-ink animate-spin" />
              <span class="text-[13px] text-faint">正在載入 PDF 原檔…</span>
            </div>

            <div v-else-if="!pdfAvailable" class="h-full flex items-center justify-center px-8">
              <div class="max-w-md rounded-xl border border-border bg-surface p-6 text-center shadow-sm">
                <p class="text-[15px] font-medium text-ink">{{ pdfError ? 'PDF 載入失敗' : '這份文件尚未保存 PDF 原檔' }}</p>
                <p class="mt-2 text-[13px] leading-relaxed text-sub">
                  {{ pdfError || '舊資料沒有 PDF 原檔。請重新上傳一次，才能在原文頁面框選影像。' }}
                </p>
              </div>
            </div>

            <div v-else class="relative min-h-full">
              <div
                v-if="loading"
                class="sticky top-0 z-30 mb-3 flex items-center gap-2 rounded-lg border px-3 py-2 text-[12px] shadow-sm"
                style="background:rgba(253,252,249,0.95);border-color:#E0DBD2;color:#6B6660"
              >
                <div class="w-3.5 h-3.5 rounded-full border-2 border-border border-t-ink animate-spin" />
                <span>{{ renderStatus }}</span>
              </div>

              <div class="pdfViewer mx-auto flex w-fit flex-col gap-5">
                <div
                  v-for="page in pdfPages"
                  :key="page.pageNum"
                  :ref="(el) => setPageRef(page.pageNum, el)"
                  class="page pdf-page bg-white shadow-sm border border-black/10"
                  :class="selectedPage === page.pageNum ? 'ring-2 ring-amber-400' : ''"
                  :data-page-num="page.pageNum"
                  :style="{ width: `${page.width}px` }"
                >
                  <div class="relative select-none" :style="{ width: `${page.width}px`, height: `${page.height}px` }">
                    <div class="page-badge absolute left-2 top-2 z-20 rounded bg-black/55 px-2 py-0.5 text-[10px] font-mono text-white">
                      Page {{ page.pageNum }}
                    </div>
                    <img
                      :ref="(el) => setImageRef(page.pageNum, el)"
                      :src="selectedDoc ? pageImageUrl(selectedDoc, page.pageNum) : ''"
                      class="absolute inset-0"
                      :style="{ width: `${page.width}px`, height: `${page.height}px` }"
                      :alt="`Page ${page.pageNum}`"
                      draggable="false"
                      @load="onPageImageLoad(page.pageNum, $event)"
                    />
                    <div
                      v-if="selectionRect && selectionRect.pageNum === page.pageNum"
                      class="selection-rect absolute z-30 border-2 border-amber-500 bg-amber-400/15 shadow-[0_0_0_9999px_rgba(0,0,0,0.12)]"
                      :style="selectionRectStyle"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      <Teleport to="body">
        <Transition name="pop">
          <div
            v-if="selectionModalOpen"
            class="fixed inset-0 z-[70] flex items-center justify-center px-6 py-6"
            @pointerdown.stop
          >
            <div class="absolute inset-0 bg-black/35" @click="closeSelectionModal" />
            <div class="relative w-[min(980px,94vw)] max-h-[86vh] overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
              <div class="flex items-center justify-between border-b border-border px-5 py-3">
                <div>
                  <p class="text-[14px] font-medium text-ink">框選影像建立 Chunk</p>
                  <p class="text-[11px] text-faint">{{ selectedDoc }} · p.{{ selectionPage || '-' }}</p>
                </div>
                <button class="text-faint hover:text-ink text-xl leading-none transition-colors" @click="closeSelectionModal">×</button>
              </div>

              <div class="grid max-h-[calc(86vh-116px)] grid-cols-[minmax(260px,0.9fr)_1.1fr] overflow-y-auto">
                <div class="border-r border-border bg-[#f3efe7] p-4">
                  <p class="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-faint">截圖</p>
                  <div class="rounded-xl border border-black/10 bg-white p-2 shadow-sm">
                    <img v-if="selectionImage" :src="selectionImage" class="max-h-[58vh] w-full object-contain" alt="框選截圖" />
                  </div>
                </div>

                <div class="flex flex-col gap-4 p-5">
                  <div v-if="selectionAnalyzing" class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-800">
                    VLM 正在讀取框選內容…
                  </div>
                  <div v-else-if="selectionError" class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
                    {{ selectionError }}
                  </div>

                  <label class="space-y-1.5">
                    <span class="text-[12px] font-medium text-sub">節點名稱</span>
                    <input
                      v-model="selectionLabel"
                      class="w-full rounded-xl border border-border bg-white px-3 py-2 text-[14px] text-ink outline-none focus:border-amber-400"
                      placeholder="例如：崩塌機制"
                    />
                  </label>

                  <label class="flex min-h-0 flex-1 flex-col space-y-1.5">
                    <span class="text-[12px] font-medium text-sub">VLM 辨識內容，可編輯後建立 chunk</span>
                    <textarea
                      v-model="selectionDescription"
                      class="min-h-[260px] w-full resize-y rounded-xl border border-border bg-white px-3 py-2 text-[14px] leading-relaxed text-ink outline-none focus:border-amber-400"
                      placeholder="VLM 辨識完成後會出現在這裡，也可以手動輸入。"
                    />
                  </label>
                </div>
              </div>

              <div class="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
                <button class="rounded-xl border border-border px-4 py-2 text-[13px] text-sub hover:bg-black/[0.03]" @click="closeSelectionModal">
                  取消
                </button>
                <button
                  class="rounded-xl px-4 py-2 text-[13px] font-medium transition-all"
                  :class="canSubmitSelection
                    ? 'bg-amber-500 text-white hover:bg-amber-600'
                    : 'bg-muted text-faint cursor-not-allowed'"
                  :disabled="!canSubmitSelection"
                  @click="submitSelectionChunk"
                >
                  {{ submitting ? '建立中…' : '確定建立 Chunk' }}
                </button>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import type { DocInfo, ManualChunkInfo, PDFInfo, VLMSelectionResponse } from '../../types/rag'

interface PdfPageView {
  pageNum: number
  width: number
  height: number
  scale: number
}

interface DragStart {
  pageNum: number
  x: number
  y: number
}

interface SelectionRect {
  pageNum: number
  x: number
  y: number
  width: number
  height: number
}

const props = defineProps<{
  show: boolean
  docs: DocInfo[]
  manualChunks: ManualChunkInfo[]
  target?: { sourceDoc: string; page: number; nonce?: number } | null
  pdfUrl: (filename: string) => string
  pageImageUrl: (filename: string, pageNum: number) => string
  fetchPdfInfo: (filename: string) => Promise<PDFInfo>
  analyzeSelection: (req: { image_b64: string; source_doc: string; source_page: number }) => Promise<VLMSelectionResponse>
  createManualChunk: (req: { text: string; label: string; source_doc: string; source_page?: number; source_anchor?: string | null }) => Promise<ManualChunkInfo>
  deleteManualChunk: (chunkId: string) => Promise<void>
}>()

const emit = defineEmits<{ close: [] }>()

const readerEl = ref<HTMLElement | null>(null)
const selectedDoc = ref<string | null>(null)
const selectedPage = ref<number | null>(null)
const loading = ref(false)
const pdfAvailable = ref(false)
const pdfError = ref('')
const pdfPages = ref<PdfPageView[]>([])
const renderStatus = ref('')
const focusedChunkId = ref<string | null>(null)
const successMsg = ref('')

const dragStart = ref<DragStart | null>(null)
const selectionRect = ref<SelectionRect | null>(null)
const selectionImage = ref('')
const selectionPage = ref(0)
const selectionModalOpen = ref(false)
const selectionAnalyzing = ref(false)
const selectionError = ref('')
const selectionLabel = ref('')
const selectionDescription = ref('')
const submitting = ref(false)

const imageRefs = new Map<number, HTMLImageElement>()
const pageRefs = new Map<number, HTMLElement>()
let renderToken = 0

const docManualChunks = computed(() =>
  props.manualChunks.filter((mc) => !selectedDoc.value || mc.source_doc === selectedDoc.value),
)

const selectionRectStyle = computed(() => {
  if (!selectionRect.value) return {}
  return {
    left: `${selectionRect.value.x}px`,
    top: `${selectionRect.value.y}px`,
    width: `${selectionRect.value.width}px`,
    height: `${selectionRect.value.height}px`,
  }
})

const canSubmitSelection = computed(() =>
  !submitting.value
  && !selectionAnalyzing.value
  && selectionLabel.value.trim().length > 0
  && selectionDescription.value.trim().length > 0,
)

watch(() => props.show, (v) => {
  if (!v) {
    resetReader()
  } else if (props.target?.sourceDoc) {
    selectDoc(props.target.sourceDoc, props.target.page || null)
  }
})

watch(() => props.target, (target) => {
  if (!props.show || !target?.sourceDoc) return
  selectDoc(target.sourceDoc, target.page || null)
}, { deep: true })

watch(() => props.docs.map((doc) => doc.filename), (filenames) => {
  if (!selectedDoc.value || filenames.includes(selectedDoc.value)) return
  resetReader()
})

function resetReader() {
  selectedDoc.value = null
  selectedPage.value = null
  pdfAvailable.value = false
  pdfError.value = ''
  renderStatus.value = ''
  pdfPages.value = []
  imageRefs.clear()
  pageRefs.clear()
  focusedChunkId.value = null
  closeSelectionModal()
  renderToken += 1
}

function setImageRef(pageNum: number, el: unknown) {
  if (el instanceof HTMLImageElement) imageRefs.set(pageNum, el)
  else imageRefs.delete(pageNum)
}

function setPageRef(pageNum: number, el: unknown) {
  if (el instanceof HTMLElement) {
    pageRefs.set(pageNum, el)
  } else {
    pageRefs.delete(pageNum)
  }
}

function onPageImageLoad(pageNum: number, event: Event) {
  const img = event.target as HTMLImageElement
  if (!img.naturalWidth || !img.naturalHeight) return
  const maxWidth = 860
  const width = Math.min(maxWidth, img.naturalWidth)
  const height = Math.round(width * (img.naturalHeight / img.naturalWidth))
  pdfPages.value = pdfPages.value.map((page) =>
    page.pageNum === pageNum ? { ...page, width, height, scale: width / img.naturalWidth } : page,
  )
}

async function selectDoc(filename: string, page: number | null = null) {
  selectedDoc.value = filename
  selectedPage.value = page
  loading.value = true
  pdfAvailable.value = false
  pdfError.value = ''
  renderStatus.value = ''
  pdfPages.value = []
  imageRefs.clear()
  pageRefs.clear()
  closeSelectionModal()
  const token = ++renderToken

  try {
    const res = await fetch(props.pdfUrl(filename), { method: 'HEAD' })
    pdfAvailable.value = res.ok
    if (!res.ok) {
      pdfError.value = res.status === 404 ? '' : `HTTP ${res.status}`
      return
    }
    await loadPdf(filename, token)
    if (page) await scrollToPage(page)
  } catch (err) {
    pdfAvailable.value = false
    pdfError.value = err instanceof Error ? err.message : '未知的 PDF 渲染錯誤'
  } finally {
    if (token === renderToken) loading.value = false
  }
}

async function loadPdf(filename: string, token: number) {
  renderStatus.value = '正在讀取 PDF 頁面…'
  const info = await props.fetchPdfInfo(filename)
  if (token !== renderToken) return
  pdfPages.value = Array.from({ length: info.total_pages }, (_, index) => ({
    pageNum: index + 1,
    width: 860,
    height: 1114,
    scale: 1,
  }))
  await nextTick()
  renderStatus.value = ''
}

function onPointerDown(event: PointerEvent) {
  if (selectionModalOpen.value || loading.value) return
  const target = event.target as HTMLElement | null
  const pageEl = target?.closest('[data-page-num]') as HTMLElement | null
  if (!pageEl) return

  const pageNum = Number(pageEl.dataset.pageNum || 0)
  if (!pageNum) return
  const rect = pageEl.getBoundingClientRect()
  const x = clamp(event.clientX - rect.left, 0, rect.width)
  const y = clamp(event.clientY - rect.top, 0, rect.height)
  dragStart.value = { pageNum, x, y }
  selectionRect.value = { pageNum, x, y, width: 0, height: 0 }
  selectedPage.value = pageNum
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
  event.preventDefault()
}

function onPointerMove(event: PointerEvent) {
  if (!dragStart.value) return
  const pageEl = pageRefs.get(dragStart.value.pageNum)
  if (!pageEl) return
  const rect = pageEl.getBoundingClientRect()
  const currentX = clamp(event.clientX - rect.left, 0, rect.width)
  const currentY = clamp(event.clientY - rect.top, 0, rect.height)
  const x = Math.min(dragStart.value.x, currentX)
  const y = Math.min(dragStart.value.y, currentY)
  selectionRect.value = {
    pageNum: dragStart.value.pageNum,
    x,
    y,
    width: Math.abs(currentX - dragStart.value.x),
    height: Math.abs(currentY - dragStart.value.y),
  }
  event.preventDefault()
}

async function onPointerUp(event: PointerEvent) {
  if (!dragStart.value || !selectionRect.value) return
  ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
  const rect = selectionRect.value
  dragStart.value = null
  if (rect.width < 14 || rect.height < 14) {
    selectionRect.value = null
    return
  }
  await analyzeCroppedSelection(rect)
}

function cancelDrag() {
  dragStart.value = null
  selectionRect.value = null
}

async function analyzeCroppedSelection(rect: SelectionRect) {
  const img = imageRefs.get(rect.pageNum)
  const page = pdfPages.value.find((p) => p.pageNum === rect.pageNum)
  if (!img || !page || !selectedDoc.value) return

  const scaleX = img.naturalWidth / page.width
  const scaleY = img.naturalHeight / page.height
  const sx = Math.max(0, Math.floor(rect.x * scaleX))
  const sy = Math.max(0, Math.floor(rect.y * scaleY))
  const sw = Math.max(1, Math.floor(rect.width * scaleX))
  const sh = Math.max(1, Math.floor(rect.height * scaleY))

  const cropCanvas = document.createElement('canvas')
  cropCanvas.width = sw
  cropCanvas.height = sh
  const ctx = cropCanvas.getContext('2d')
  if (!ctx) return
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh)
  selectionImage.value = cropCanvas.toDataURL('image/png')
  selectionPage.value = rect.pageNum
  selectionLabel.value = ''
  selectionDescription.value = ''
  selectionError.value = ''
  selectionModalOpen.value = true
  selectionAnalyzing.value = true

  try {
    const result = await props.analyzeSelection({
      image_b64: selectionImage.value,
      source_doc: selectedDoc.value,
      source_page: rect.pageNum,
    })
    selectionLabel.value = result.label
    selectionDescription.value = result.description
  } catch (err) {
    selectionError.value = err instanceof Error ? err.message : 'VLM 辨識失敗，請手動輸入內容。'
  } finally {
    selectionAnalyzing.value = false
  }
}

function closeSelectionModal() {
  selectionModalOpen.value = false
  selectionAnalyzing.value = false
  selectionError.value = ''
  selectionImage.value = ''
  selectionPage.value = 0
  selectionLabel.value = ''
  selectionDescription.value = ''
  selectionRect.value = null
  dragStart.value = null
}

async function submitSelectionChunk() {
  if (!canSubmitSelection.value || !selectedDoc.value) return
  submitting.value = true
  const label = selectionLabel.value.trim()
  try {
    await props.createManualChunk({
      text: selectionDescription.value.trim(),
      label,
      source_doc: selectedDoc.value,
      source_page: selectionPage.value,
      source_anchor: selectionPage.value ? `^p${selectionPage.value}` : null,
    })
    successMsg.value = `「${label}」已建立`
    setTimeout(() => { successMsg.value = '' }, 3000)
    closeSelectionModal()
  } finally {
    submitting.value = false
  }
}

function chunkPage(chunk: ManualChunkInfo): number {
  if (chunk.source_page && chunk.source_page > 0) return chunk.source_page
  const match = chunk.source_anchor?.match(/\^p(\d+)/)
  return match ? Number(match[1]) : 0
}

async function goToChunkSource(chunk: ManualChunkInfo) {
  const page = chunkPage(chunk)
  focusedChunkId.value = chunk.chunk_id
  if (chunk.source_doc && chunk.source_doc !== selectedDoc.value) {
    await selectDoc(chunk.source_doc, page || null)
  } else {
    selectedPage.value = page || null
    if (page) await scrollToPage(page)
  }
}

async function scrollToPage(page: number) {
  await nextTick()
  const el = pageRefs.get(page)
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

onUnmounted(() => {
  renderToken += 1
})
</script>

<style scoped>
.reader-body {
  cursor: crosshair;
  user-select: none;
  -webkit-user-select: none;
}
.page-badge {
  user-select: none;
  -webkit-user-select: none;
  pointer-events: none;
}
.selection-rect {
  pointer-events: none;
}
.pop-enter-active { transition: opacity 0.12s ease, transform 0.12s ease; }
.pop-leave-active { transition: opacity 0.08s ease, transform 0.08s ease; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(4px) scale(0.97); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
