<script setup>
import { duration, events, nodes, statuses, timestamp, tools } from '../format.js'
defineProps({ items: { type: Array, default: () => [] } })
</script>

<template>
  <ol v-if="items.length" class="timeline">
    <li v-for="event in items" :key="event.event_id"
      :class="{ failed: event.event_type.endsWith('FAILED'), replanned: event.event_type.startsWith('REPLAN_') }">
      <div class="timeline-line">
        <strong>{{ events[event.event_type] ?? event.event_type }}</strong>
        <small>{{ duration(event.duration_ms) }}</small>
      </div>
      <p>
        {{ tools[event.payload?.tool_name] ?? nodes[event.node_name] ?? '' }}
        <span v-if="event.payload?.status">{{ statuses[event.payload.status] ?? event.payload.status }}</span>
        <span v-if="event.payload?.replan_count != null"> · 재계획 {{ event.payload.replan_count }}회</span>
        <span v-if="event.payload?.code === 'RATE_LIMITED'"> · 호출 제한</span>
        <span v-if="event.payload?.code === 'AUTH_FAILED'"> · 서버 API 키 설정 확인 필요</span>
      </p>
      <p v-if="event.reason_summary">{{ event.reason_summary }}</p>
      <small>{{ timestamp(event.timestamp) }}</small>
    </li>
  </ol>
  <p v-else class="empty">표시할 실행 이벤트가 없습니다.</p>
</template>
