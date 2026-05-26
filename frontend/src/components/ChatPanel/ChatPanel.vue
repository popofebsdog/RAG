<template>
  <div class="flex flex-col h-full overflow-hidden" style="background:#F8FAFC">
    <!-- Header -->
    <div class="h-[52px] shrink-0 flex items-center px-4 border-b" style="border-color:#D7DEE8">
      <p class="text-[13px] font-semibold" style="color:#172033">{{ lang === 'zh' ? '詢問文件' : 'Ask the Document' }}</p>
    </div>

    <!-- Messages -->
    <div ref="messagesEl" class="flex-1 overflow-y-auto p-3 space-y-2.5">
      <div v-if="messages.length === 0" class="text-center pt-10">
        <div class="w-9 h-9 rounded-full flex items-center justify-center mx-auto mb-3" style="background:#EEF3F8">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#667085" stroke-width="1.5" stroke-linecap="round">
            <path d="M2 3h12v8H9l-3 3V11H2z"/>
          </svg>
        </div>
        <p class="text-[13px]" style="color:#667085">{{ emptyPrompt }}</p>
      </div>

      <template v-for="msg in messages" :key="msg.id">
        <!-- User bubble -->
        <div v-if="msg.role === 'user'" class="flex justify-end">
          <div class="rounded-lg rounded-tr-sm px-3 py-2 max-w-[260px] text-[14px] leading-relaxed" style="background:#172033;color:#fff">
            {{ msg.content }}
          </div>
        </div>

        <!-- Assistant bubble -->
        <div v-else class="space-y-1.5">
          <div class="rounded-lg rounded-tl-sm px-3 py-2 text-[14px] leading-relaxed border" style="background:#FFFFFF;border-color:#D7DEE8;color:#172033">
            {{ msg.content }}
          </div>

        </div>
      </template>

      <!-- Loading dots -->
      <div v-if="querying" class="flex items-center gap-1.5 px-1">
        <span v-for="i in 3" :key="i"
          class="w-1.5 h-1.5 rounded-full animate-blink"
          style="background:#A9A39A"
          :style="{ animationDelay: (i-1)*0.15 + 's' }" />
      </div>
    </div>

    <!-- Input -->
    <div class="border-t p-3" style="border-color:#D7DEE8">
      <form class="flex gap-2" @submit.prevent="submit">
        <input
          v-model="input"
          type="text"
          :placeholder="lang === 'zh' ? '輸入問題…' : 'Ask anything…'"
          :disabled="!canQuery || querying"
          class="flex-1 rounded-lg px-3 py-2 text-[14px] outline-none disabled:opacity-40 border"
          style="background:#FFFFFF;border-color:#D7DEE8;color:#172033"
        />
        <button
          type="submit"
          :disabled="!canQuery || querying || !input.trim()"
          class="px-3 py-2 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:opacity-80 transition-opacity"
          style="background:#1E4E8C;color:#fff"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <path d="M13.5 8L3 4l2.5 4L3 12z"/>
          </svg>
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, watch } from 'vue'
import type { QueryResponse } from '../../types/rag'

const props = defineProps<{
  canQuery: boolean
  querying: boolean
  queryResult: QueryResponse | null
  error: string | null
  lang: 'en' | 'zh'
}>()

const emit = defineEmits<{ query: [question: string] }>()

const emptyPrompt = computed(() => {
  if (props.canQuery) return props.lang === 'zh' ? '可以開始詢問這份文件' : 'Ready for questions'
  return props.lang === 'zh' ? '上傳 PDF 後即可提問' : 'Upload a PDF to start'
})

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<Message[]>([])
const input = ref('')
const messagesEl = ref<HTMLElement | null>(null)
let msgId = 0

function submit() {
  const q = input.value.trim()
  if (!q || !props.canQuery || props.querying) return
  messages.value.push({ id: msgId++, role: 'user', content: q })
  input.value = ''
  emit('query', q)
  scrollToBottom()
}

watch(() => props.queryResult, (result) => {
  if (!result) return
  messages.value.push({
    id: msgId++,
    role: 'assistant',
    content: result.answer,
  })
  scrollToBottom()
})

watch(() => props.error, (err) => {
  if (!err) return
  messages.value.push({ id: msgId++, role: 'assistant', content: `Error: ${err}` })
  scrollToBottom()
})

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}
</script>

<style scoped>
</style>
