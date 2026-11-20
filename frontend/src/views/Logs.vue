<script setup>
import { computed, ref, watch } from 'vue'
import Timeline from '../components/Timeline.vue'
import { api, session } from '../state.js'
import { errorMessage } from '../api.js'
import { duration, statuses, timestamp } from '../format.js'

const sessions = ref([])
const selected = ref(null)
const detail = ref(null)
const runId = ref(null)
const busy = ref(false)
const confirming = ref(false)
const error = ref('')
let version = 0
const run = computed(() => detail.value?.runs.find((item) => item.id === runId.value))
const events = computed(() => detail.value?.events.filter((item) => item.run_id === runId.value) ?? [])
const elapsed = computed(() => run.value?.finished_at
  ? new Date(run.value.finished_at) - new Date(run.value.started_at) : null)

async function perform(operation) {
  if (session.status !== 'active' || busy.value) return
  const current = ++version
  busy.value = true
  error.value = ''
  try { await operation(() => current === version) }
  catch (failure) { if (current === version) error.value = errorMessage(failure) }
  finally { if (current === version) busy.value = false }
}

async function fetchDetail(id, current) {
  const result = await api.request('/logs/' + id)
  if (!current()) return
  detail.value = result
  runId.value = result.runs.at(-1)?.id ?? null
}

function load() {
  return perform(async (current) => {
    const result = await api.request('/logs')
    if (!current()) return
    sessions.value = result.items
    selected.value = result.items[0]?.session_id ?? null
    detail.value = runId.value = null
    if (selected.value) await fetchDetail(selected.value, current)
  })
}

function remove() {
  return perform(async (current) => {
    await api.request('/logs/' + selected.value, { method: 'DELETE' })
    if (!current()) return
    sessions.value = []
    selected.value = detail.value = runId.value = null
    confirming.value = false
  })
}

watch(() => [session.status, session.epoch], () => {
  ++version
  sessions.value = []
  selected.value = detail.value = runId.value = null
  busy.value = confirming.value = false
  error.value = ''
  if (session.status === 'active') load()
}, { immediate: true })
</script>

<template>
  <header class="page-header"><h1>실행 기록</h1><button :disabled="busy || session.status !== 'active'" @click="load">새로고침</button></header>
  <p v-if="error" class="error-box" role="alert">{{ error }}</p>
  <div class="management">
    <section class="panel list-panel">
      <div class="panel-heading"><h2>이 세션의 실행</h2><small v-if="sessions.length">{{ sessions[0].run_count }}건</small></div>
      <p v-if="busy" class="loading" role="status">기록을 처리하고 있습니다.</p>
      <p v-else-if="!sessions.length && !error" class="empty">아직 저장된 실행 기록이 없습니다.</p>
      <ul v-if="detail?.runs.length" class="selection-list">
        <li v-for="item in [...detail.runs].reverse()" :key="item.id">
          <button :aria-pressed="item.id === runId" @click="runId = item.id">
            <strong>{{ statuses[item.status] }}</strong><small>{{ timestamp(item.started_at) }}</small>
          </button>
        </li>
      </ul>
      <button v-if="selected" class="danger" :disabled="busy" @click="confirming = true">이 세션 기록 삭제</button>
      <div v-if="confirming" class="warning-box">
        <p>이 세션의 전체 실행 기록을 삭제할까요?</p>
        <div class="actions"><button class="danger" :disabled="busy" @click="remove">기록 삭제 확인</button><button @click="confirming = false">취소</button></div>
      </div>
    </section>
    <section class="panel detail-panel">
      <div class="panel-heading"><h2>실행 타임라인</h2><span v-if="run" class="chip">{{ statuses[run.status] }}</span></div>
      <p v-if="run" class="callout">소요 {{ duration(elapsed) }} · 재계획 {{ run.replan_count }}회 <span v-if="run.safe_error_code === 'RATE_LIMITED'">· AI 서비스 호출 제한</span></p>
      <Timeline :items="events" />
    </section>
  </div>
</template>
