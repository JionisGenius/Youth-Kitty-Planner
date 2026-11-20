<script setup>
import { computed } from 'vue'
import { duration, events, nodes, statuses, timestamp, tools } from '../format.js'
import UiIcon from './UiIcon.vue'
const props = defineProps({ items: { type: Array, default: () => [] }, compact: Boolean })
const hiddenStages = new Set(['NODE_STARTED', 'NODE_FINISHED', 'TOOL_REQUESTED'])
const markerIcons = {
  NODE_FINISHED: 'check', TOOL_SUCCEEDED: 'check', RUN_FINISHED: 'check',
  TOOL_FAILED: 'cross', RUN_FAILED: 'cross',
  REPLAN_STARTED: 'repeat', REPLAN_EXHAUSTED: 'repeat',
}
const visibleItems = computed(() => props.items.flatMap((event) => {
  const failedNode = event.event_type === 'NODE_FINISHED' && event.payload?.outcome === 'FAILED'
  if (props.compact && hiddenStages.has(event.event_type) && !failedNode) return []
  return [{
    event,
    icon: failedNode ? 'cross' : markerIcons[event.event_type],
    label: failedNode ? '단계 실패' : (events[event.event_type] ?? event.event_type),
  }]
}))
</script>

<template>
  <ol v-if="visibleItems.length" class="timeline">
    <li v-for="{ event, icon, label } in visibleItems" :key="event.event_id"
      :class="{ failed: icon === 'cross', replanned: icon === 'repeat', succeeded: icon === 'check' }">
      <div class="timeline-marker" aria-hidden="true"><UiIcon v-if="icon" :name="icon" /></div>
      <div class="timeline-line">
        <strong>{{ label }}</strong>
        <small v-if="event.duration_ms != null">{{ duration(event.duration_ms) }}</small>
      </div>
      <p>
        {{ tools[event.payload?.tool_name] ?? nodes[event.node_name] ?? '' }}
        <span v-if="event.payload?.status">{{ statuses[event.payload.status] ?? event.payload.status }}</span>
        <span v-if="event.payload?.replan_count != null"> · 재계획 {{ event.payload.replan_count }}회</span>
        <span v-if="event.payload?.code === 'RATE_LIMITED'"> · 호출 제한</span>
        <span v-if="event.payload?.code === 'AUTH_FAILED'"> · 서버 API 키 설정 확인 필요</span>
      </p>
      <p v-if="compact && event.reason_summary">{{ event.reason_summary }}</p>
      <details v-if="!compact" class="event-details">
        <summary>이벤트 상세</summary>
        <time :datetime="event.timestamp">{{ timestamp(event.timestamp) }}</time>
        <p v-if="event.reason_summary">{{ event.reason_summary }}</p>
      </details>
    </li>
  </ol>
  <p v-else class="empty">표시할 실행 이벤트가 없습니다.</p>
</template>
