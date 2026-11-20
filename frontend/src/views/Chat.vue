<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Timeline from '../components/Timeline.vue'
import { api, conversation, session } from '../state.js'
import { errorMessage } from '../api.js'
import { rules, statuses } from '../format.js'

const route = useRoute()
const router = useRouter()
const input = ref('')
const textarea = ref(null)
const latest = ref(null)
const timeline = ref([])
const timelineState = ref('idle')
const samples = ['서울에서 독립 준비 계획을 세워줘', '보증금과 월세 예산을 비교하고 싶어', '월세를 55만원으로 바꿔줘']
const latestReply = computed(() => conversation.entries.findLast((entry) => entry.reply)?.reply)

function suggest(value) {
  input.value = value
  textarea.value?.focus()
}

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
  nextTick(() => latest.value?.scrollIntoView({ block: 'nearest' }))
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
  <header class="page-header">
    <h1>AI 플래너</h1>
  </header>
  <section class="hero">
    <div>
      <h2>나만의 첫 독립,<br><em>차근차근 준비해요.</em></h2>
      <p>희망 지역, 보증금과 월세, 출근 일정을 알려주세요.<br class="desktop-only"> 과거 전월세 사례와 준비 조건을 함께 살펴볼게요.</p>
    </div>
    <div class="hero-art" aria-hidden="true">
      <span class="orbit orbit-outer"></span><span class="orbit orbit-inner"></span>
      <span class="sparkle sparkle-one">✦</span><span class="sparkle sparkle-two">✧</span>
      <span class="cat"><i></i><i></i><b></b></span>
    </div>
  </section>

  <div class="dashboard">
    <section class="panel chat-panel" aria-labelledby="chat-title">
      <div class="panel-heading"><h2 id="chat-title">플래너와 대화</h2></div>
      <p v-if="route.query.plan" class="callout">선택한 저장 계획의 조건을 바탕으로 대화합니다. <RouterLink to="/">일반 대화로 돌아가기</RouterLink></p>
      <div v-if="conversation.entries.length" class="conversation" aria-live="polite">
        <article v-for="(entry, index) in conversation.entries" :key="index" :class="['message', entry.role]">
          <strong>{{ entry.role === 'user' ? '나' : entry.role === 'error' ? '요청 실패' : '청년냥이' }}</strong>
          <p>{{ entry.message }}</p>
          <span v-if="entry.reply" class="chip">{{ statuses[entry.reply.status] ?? entry.reply.status }}</span>
          <p v-if="entry.reply?.tool_summaries.some((step) => step.error_code === 'AUTH_FAILED')" class="callout">
            일부 조회를 완료하지 못했습니다. 서버의 외부 API 키 설정을 확인해 주세요.
          </p>
        </article>
        <div ref="latest"></div>
      </div>
      <div v-else class="suggestions" aria-label="예시 요청">
        <button v-for="sample in samples" :key="sample" type="button" @click="suggest(sample)">{{ sample }}</button>
      </div>
      <p v-if="conversation.pending" class="loading" role="status"><span class="spinner"></span> 요청을 처리하고 있습니다. 응답이 끝나면 실행 기록이 표시됩니다.</p>
      <form class="composer" @submit.prevent="send">
        <label for="message" class="sr-only">플래너에게 보낼 메시지</label>
        <textarea id="message" ref="textarea" v-model="input" rows="2" maxlength="4000"
          placeholder="희망 지역과 예산을 입력해 주세요"></textarea>
        <button class="primary" :disabled="!input.trim() || conversation.pending || session.status !== 'active'">보내기</button>
      </form>
      <RouterLink v-if="conversation.draft && !conversation.draftSaved" to="/plans?draft=1" class="draft-link">계획 초안 검토 및 저장</RouterLink>
      <p v-else-if="conversation.draftSaved" class="callout">초안을 저장했습니다. <RouterLink to="/plans">내 계획 보기</RouterLink></p>
    </section>

    <aside class="support">
      <section class="panel evidence">
        <div class="panel-heading"><h2>판정과 근거</h2></div>
        <p class="muted">전월세 자료는 과거 신고 계약입니다.</p>
        <ul v-if="latestReply?.evaluations.length" class="checks">
          <li v-for="(item, index) in latestReply.evaluations" :key="index">
            <span>{{ rules[item.rule_code] ?? item.rule_code }}</span>
            <span :class="['chip', item.status.toLowerCase()]">{{ item.status === 'UNKNOWN' ? 'UNKNOWN' : statuses[item.status] }}</span>
            <small v-if="item.caveat">{{ item.caveat }}</small>
          </li>
        </ul>
        <p v-else class="empty">대화가 완료되면 확인한 조건이 여기에 표시됩니다.</p>
      </section>
      <section class="panel execution-card">
        <div class="panel-heading"><h2>최근 실행</h2><RouterLink to="/logs">전체 기록</RouterLink></div>
        <p v-if="timelineState === 'loading'" class="loading" role="status">실행 기록을 불러오고 있습니다.</p>
        <p v-else-if="timelineState === 'error'" class="error-box" role="alert">실행 기록을 불러오지 못했습니다.</p>
        <div v-else-if="timelineState === 'ready'" class="timeline-preview"><Timeline :items="timeline" /></div>
        <p v-else class="empty">요청 처리 후 서버에 저장된 실행 단계가 표시됩니다.</p>
      </section>
    </aside>
  </div>
</template>
