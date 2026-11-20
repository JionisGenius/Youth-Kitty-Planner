<script setup>
import { computed, ref, watch } from 'vue'
import Timeline from '../components/Timeline.vue'
import UiIcon from '../components/UiIcon.vue'
import { api, session } from '../state.js'
import { errorMessage } from '../api.js'
import { anomalyCauses, anomalyFindings, duration, intents, statuses, timestamp } from '../format.js'

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
const anomaly = computed(() => events.value.at(-1)?.payload?.anomaly)
const showAll = ref(false)
watch(runId, () => { showAll.value = false })
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
  <header class="page-header">
    <div><h1>실행 기록</h1><p>AI가 어떤 자료를 찾았고 어떻게 판단했는지 확인하세요.</p></div>
    <button :disabled="busy || session.status !== 'active'" @click="load"><UiIcon name="repeat" />새로고침</button>
  </header>
  <p v-if="error" class="error-box" role="alert">{{ error }}</p>
  <div class="management logs-layout">
    <section class="panel list-panel">
      <div class="panel-heading"><h2>이 세션의 실행</h2><span v-if="sessions.length" class="chip neutral">{{ sessions[0].run_count }}건</span></div>
      <p v-if="busy" class="loading" role="status">기록을 처리하고 있습니다.</p>
      <p v-else-if="!sessions.length && !error" class="empty">아직 저장된 실행 기록이 없습니다.</p>
      <ul v-if="detail?.runs.length" class="selection-list">
        <li v-for="item in [...detail.runs].reverse()" :key="item.id">
          <button class="run-card" :aria-pressed="item.id === runId" @click="runId = item.id">
            <span class="run-card-title"><strong>{{ intents[item.intent] ?? '플래너 실행' }}</strong><span :class="['chip', item.status.toLowerCase()]">{{ statuses[item.status] }}</span></span>
            <small>{{ timestamp(item.started_at) }}</small>
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
      <div class="panel-heading"><h2>실행 타임라인</h2><span v-if="run" :class="['chip', run.status.toLowerCase()]">{{ statuses[run.status] }}</span></div>
      <template v-if="run">
        <dl class="metrics run-metrics">
          <div><dt>소요 시간</dt><dd>{{ duration(elapsed) }}</dd></div>
          <div><dt>대안 탐색</dt><dd>{{ run.replan_count }}회</dd></div>
          <div><dt>실행 점검</dt><dd>{{ anomaly?.status === 'ANOMALOUS' ? '이상 징후' : anomaly?.status === 'NORMAL' ? '정상' : '판정 불가' }}</dd></div>
        </dl>
        <p v-if="run.safe_error_code === 'RATE_LIMITED'" class="error-box">AI 서비스 호출 한도에 도달했습니다.</p>
        <section v-if="anomaly?.status === 'ANOMALOUS'" class="anomaly-box" aria-labelledby="anomaly-title">
          <h3 id="anomaly-title" class="notice-heading"><UiIcon name="warning" />실행 이상 징후</h3>
          <ul><li v-for="code in Object.keys(anomaly.findings ?? {})" :key="code">{{ anomalyFindings[code] ?? '실행 기록 확인 필요' }}</li></ul>
          <p v-if="anomaly.diagnosis?.status === 'COMPLETED'">AI 원인 분류 · {{ anomalyCauses[anomaly.diagnosis.cause] ?? '추가 확인 필요' }}</p>
          <p v-else>AI 원인 분석 미완료<span v-if="anomaly.diagnosis?.code === 'RATE_LIMITED'"> · 호출 한도</span></p>
        </section>
        <div class="timeline-toolbar">
          <h3>실행 순서</h3>
          <button type="button" aria-controls="run-timeline" :aria-pressed="showAll" @click="showAll = !showAll">{{ showAll ? '주요 단계 보기' : '모든 단계 보기' }}</button>
        </div>
        <div id="run-timeline"><Timeline :items="events" :compact="!showAll" /></div>
      </template>
      <div v-else class="empty detail-empty">
        <span class="mini-icon"><UiIcon name="clipboard" /></span>
        <h3>표시할 실행이 없습니다</h3>
        <p>AI 플래너에 요청하면 여기에서 실행 순서를 볼 수 있어요.</p>
      </div>
    </section>
  </div>
</template>
