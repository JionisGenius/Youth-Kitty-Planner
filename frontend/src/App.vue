<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { api, session } from './state.js'
import { errorMessage } from './api.js'

const notice = ref('')
let expiryTimer
async function connect() {
  notice.value = ''
  try { await api.startSession() }
  catch (error) { notice.value = errorMessage(error) }
}

onMounted(() => {
  if (session.status === 'new') connect()
  expiryTimer = window.setInterval(api.checkSession, 15000)
  window.addEventListener('focus', api.checkSession)
})
onUnmounted(() => {
  clearInterval(expiryTimer)
  window.removeEventListener('focus', api.checkSession)
})
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <RouterLink to="/" class="brand">
        <span class="brand-icon" aria-hidden="true">✦</span>
        <span><strong>Youth Kitty Planner</strong><small>청년냥이 플래너</small></span>
      </RouterLink>
      <nav aria-label="메인 메뉴">
        <RouterLink to="/" exact-active-class="selected"><span aria-hidden="true">✦</span> AI 플래너</RouterLink>
        <RouterLink to="/plans"><span aria-hidden="true">▤</span> 내 계획</RouterLink>
        <RouterLink to="/logs"><span aria-hidden="true">◷</span> 실행 기록</RouterLink>
      </nav>
      <div class="sidebar-session"><span :class="{ online: session.status === 'active' }"></span>{{ session.status === 'active' ? '세션 연결됨' : '세션 연결 필요' }}</div>
    </aside>
    <main class="workspace">
      <div v-if="session.status !== 'active'" class="session-banner" role="status">
        <div>
          <strong>{{ session.starting ? '세션 연결 중' : session.status === 'expired' ? '세션이 만료되었습니다' : '플래너 연결이 필요합니다' }}</strong>
          <p v-if="notice">{{ notice }}</p>
          <p v-else-if="session.status === 'expired'">새 세션에서는 이전 세션의 계획과 실행 기록에 접근할 수 없습니다.</p>
        </div>
        <button class="primary" :disabled="session.starting" @click="connect">새 세션 시작</button>
      </div>
      <RouterView />
    </main>
  </div>
</template>
