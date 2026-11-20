<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Timeline from '../components/Timeline.vue'
import UiIcon from '../components/UiIcon.vue'
import { api, conversation, session } from '../state.js'
import { errorMessage } from '../api.js'
import { evaluationValue, money, providers, rules, statuses } from '../format.js'

const route = useRoute()
const router = useRouter()
const input = ref('')
const textarea = ref(null)
const messages = ref(null)
const timeline = ref([])
const timelineState = ref('idle')
const samples = [
  ['home', '첫 출근 전 독립 계획', '서울 종로구(11110)에서 첫 독립을 준비하고 있어. 보증금 3000만원, 월세 60만원으로 출근 전 독립 준비 계획을 세워줘.'],
  ['wallet', '예산에 맞는 지역 비교', '서울 종로구(11110)를 희망하고 대안으로 서울 중구(11140)도 가능해. 보증금 3000만원, 월세 60만원 예산에 맞는 과거 전월세 사례를 비교해 줘.'],
  ['calendar', '독립 준비 일정 만들기', '서울 종로구(11110)에서 독립을 준비하고 있어. 준비 기간 7일로 일정을 만들어 줘.'],
]
const latestReply = computed(() => conversation.entries.findLast((entry) => entry.reply)?.reply)
const constraints = computed(() => latestReply.value?.constraints ?? {})
const sources = computed(() => {
  const terminal = timeline.value.at(-1)
  if (!terminal || terminal.run_id !== latestReply.value?.run_id) return []
  const reported = terminal.payload?.evidence?.sources ?? []
  return [...new Map(reported.filter((source) => providers[source.provider])
    .map((source) => [source.provider, source])).values()]
})

function suggest(value) {
  input.value = value
  focusComposer()
}

function revealComposer() {
  textarea.value?.scrollIntoView({ block: 'nearest' })
}

function focusComposer() {
  textarea.value?.focus({ preventScroll: true })
  revealComposer()
}

function keepComposerVisible() {
  if (document.activeElement === textarea.value) revealComposer()
}

onMounted(() => {
  window.visualViewport?.addEventListener('resize', keepComposerVisible)
  scrollToLatest()
})
onUnmounted(() => window.visualViewport?.removeEventListener('resize', keepComposerVisible))

watch(() => session.epoch, () => { input.value = '' })
watch(() => conversation.runId, async (runId, _, onCleanup) => {
  let current = true
  onCleanup(() => { current = false })
  timeline.value = []
  timelineState.value = runId ? 'loading' : 'idle'
  if (!runId) return
  try {
    const result = await api.request('/runs/' + runId + '/events')
    if (current) {
      timeline.value = result
      timelineState.value = 'ready'
    }
  } catch {
    if (current) timelineState.value = 'error'
  }
}, { immediate: true })

function scrollToLatest() {
  nextTick(() => {
    if (messages.value) messages.value.scrollTop = messages.value.scrollHeight
  })
}

async function send() {
  const message = input.value.trim()
  if (!message || conversation.pending || session.status !== 'active') return
  const epoch = session.epoch
  const body = { message }
  if (typeof route.query.plan === 'string') body.base_plan_id = route.query.plan
  conversation.entries.push({ role: 'user', message })
  conversation.pending = true
  conversation.runId = null
  input.value = ''
  scrollToLatest()
  try {
    const reply = await api.request('/chat', { method: 'POST', body })
    if (epoch !== session.epoch) return
    conversation.entries.push({ role: 'assistant', message: reply.assistant_message, reply })
    conversation.runId = reply.run_id
    if (body.base_plan_id && route.query.plan === body.base_plan_id && reply.status !== 'NEEDS_INPUT') router.replace('/')
    if (reply.draft_plan) {
      conversation.draft = { ...reply.draft_plan, runId: reply.run_id }
      conversation.draftSaved = false
    }
  } catch (error) {
    if (epoch !== session.epoch) return
    conversation.entries.push({ role: 'error', message: errorMessage(error) })
    conversation.runId = error.runId
  } finally {
    if (epoch === session.epoch) {
      conversation.pending = false
      scrollToLatest()
    }
  }
}
</script>

<template>
  <header class="hero">
    <div class="hero-copy">
      <h1>첫 독립, <em>막막함을 계획으로.</em></h1>
      <p>예산부터 지역, 출근 일정까지. 청년냥이가 실제 데이터를 바탕으로 너의 첫 독립을 함께 준비해.</p>
      <button type="button" class="hero-action" @click="focusComposer">나의 독립 계획 시작하기 <UiIcon name="down" /></button>
    </div>
  </header>

  <div class="dashboard">
    <section class="panel chat-panel" aria-labelledby="chat-title">
      <div class="panel-heading chat-heading">
        <UiIcon name="sparkle" />
        <h2 id="chat-title">청년냥이와 대화</h2>
      </div>
      <p v-if="route.query.plan" class="callout">선택한 저장 계획의 조건을 바탕으로 대화합니다. <RouterLink to="/">일반 대화로 돌아가기</RouterLink></p>
      <div v-show="conversation.entries.length" ref="messages" class="conversation" role="log" tabindex="0" aria-label="플래너 대화 기록">
        <TransitionGroup name="message" tag="div" class="message-list">
          <article v-for="(entry, index) in conversation.entries" :key="index" :class="['message', entry.role]">
            <header class="message-heading">
              <strong>{{ entry.role === 'user' ? '나' : entry.role === 'error' ? '요청 실패' : '청년냥이' }}</strong>
              <span v-if="entry.reply" :class="['chip', entry.reply.status.toLowerCase()]">{{ statuses[entry.reply.status] ?? entry.reply.status }}</span>
            </header>
            <p>{{ entry.message }}</p>
            <p v-if="entry.reply?.tool_summaries.some((step) => step.error_code === 'AUTH_FAILED')" class="callout">
              일부 조회를 완료하지 못했습니다. 서버의 외부 API 키 설정을 확인해 주세요.
            </p>
          </article>
        </TransitionGroup>
      </div>
      <div v-if="!conversation.entries.length" class="welcome">
        <div class="welcome-intro">
          <span class="avatar" aria-hidden="true"><i class="kitten-mark"></i></span>
          <div>
            <h3>어떤 준비부터 시작할까요?</h3>
            <p>시작 질문을 골라 내 상황에 맞게 수정해 보세요.</p>
          </div>
        </div>
        <div class="suggestions" aria-label="예시 요청">
          <button v-for="[icon, label, message] in samples" :key="label" type="button" @click="suggest(message)">
            <UiIcon :name="icon" /><span>{{ label }}</span><UiIcon name="arrow" />
          </button>
        </div>
      </div>
      <p v-if="conversation.pending" class="loading" role="status"><span class="spinner" aria-hidden="true"></span>요청을 처리하고 있습니다. 완료되면 실행 기록을 표시해요.</p>
      <form class="composer" @submit.prevent="send">
        <label for="message" class="sr-only">플래너에게 보낼 메시지</label>
        <textarea id="message" ref="textarea" v-model="input" rows="2" maxlength="4000"
          placeholder="희망 지역과 예산을 입력해 주세요"></textarea>
        <button class="primary" :disabled="!input.trim() || conversation.pending || session.status !== 'active'">보내기 <UiIcon name="send" /></button>
      </form>
      <RouterLink v-if="conversation.draft && !conversation.draftSaved" to="/plans?draft=1" class="draft-link">계획 초안 검토 및 저장 <span aria-hidden="true">→</span></RouterLink>
      <p v-else-if="conversation.draftSaved" class="callout">초안을 저장했습니다. <RouterLink to="/plans">내 계획 보기</RouterLink></p>
    </section>

    <aside class="support">
      <section class="panel conditions" aria-labelledby="conditions-title">
        <div class="panel-heading"><h2 id="conditions-title">현재 계획 조건</h2><UiIcon name="wallet" /></div>
        <dl class="metrics budget-metrics">
          <div><dt>보증금 상한</dt><dd>{{ money(constraints.max_deposit_krw) }}</dd></div>
          <div><dt>월세 상한</dt><dd>{{ money(constraints.max_monthly_rent_krw) }}</dd></div>
        </dl>
        <dl class="condition-details">
          <div><dt><UiIcon name="pin" />희망 지역</dt><dd>{{ constraints.residential_preferences?.map((area) => area.label).join(', ') || '미정' }}</dd></div>
          <div><dt><UiIcon name="calendar" />준비 기간</dt><dd>{{ constraints.preparation_days == null ? '미정' : constraints.preparation_days + '일' }}</dd></div>
        </dl>
      </section>
      <section class="panel evidence">
        <div class="panel-heading"><h2>판정과 근거</h2><UiIcon name="search" /></div>
        <p class="evidence-note"><strong>과거 신고 계약 기준</strong>현재 임대 가능 여부는 별도로 확인이 필요합니다.</p>
        <ul v-if="latestReply?.evaluations.length" class="checks">
          <li v-for="(item, index) in latestReply.evaluations" :key="index">
            <span>{{ rules[item.rule_code] ?? item.rule_code }}</span>
            <span :class="['chip', item.status.toLowerCase()]">{{ statuses[item.status] ?? item.status }}</span>
            <small v-if="item.expected_value != null">
              {{ item.rule_code === 'PLAN_TIMELINE' ? '출근일' : '상한' }} {{ evaluationValue(item.rule_code, item.expected_value) }}
              · {{ item.rule_code === 'PLAN_TIMELINE' ? '준비 종료' : '확인값' }} {{ evaluationValue(item.rule_code, item.observed_value) }}
            </small>
            <small v-if="item.caveat">{{ item.caveat }}</small>
          </li>
        </ul>
        <p v-else class="empty">대화가 완료되면 확인한 조건이 여기에 표시됩니다.</p>
        <ul v-if="sources.length" class="source-list" aria-label="확인한 자료 출처">
          <li v-for="source in sources" :key="source.provider">
            <a v-if="source.url?.startsWith('https://')" :href="source.url" target="_blank" rel="noopener noreferrer" :aria-label="providers[source.provider] + ' (새 탭)'">{{ providers[source.provider] }} <span aria-hidden="true">↗</span></a>
            <span v-else>{{ providers[source.provider] }}</span>
          </li>
        </ul>
      </section>
      <section class="panel execution-card">
        <div class="panel-heading"><h2>최근 실행</h2><RouterLink to="/logs">전체 기록</RouterLink></div>
        <p v-if="timelineState === 'loading'" class="loading" role="status">실행 기록을 불러오고 있습니다.</p>
        <p v-else-if="timelineState === 'error'" class="error-box" role="alert">실행 기록을 불러오지 못했습니다.</p>
        <div v-else-if="timelineState === 'ready'" class="timeline-preview" tabindex="0" aria-label="최근 실행 주요 단계"><Timeline :items="timeline" compact /></div>
        <p v-else class="empty">요청 처리 후 서버에 저장된 실행 단계가 표시됩니다.</p>
      </section>
    </aside>
  </div>
</template>
