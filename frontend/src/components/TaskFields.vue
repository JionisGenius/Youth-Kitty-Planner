<script setup>
import { statuses } from '../format.js'
defineProps({
  task: { type: Object, required: true },
  idPrefix: { type: String, required: true },
})
</script>

<template>
  <div class="form-grid">
    <label :for="idPrefix + '-title'">작업 이름
      <input :id="idPrefix + '-title'" v-model.trim="task.title" required maxlength="160">
    </label>
    <label :for="idPrefix + '-date'">작업 날짜
      <input :id="idPrefix + '-date'" v-model="task.task_date" type="date" required>
    </label>
    <label class="wide" :for="idPrefix + '-description'">설명
      <input :id="idPrefix + '-description'" v-model.trim="task.description" maxlength="2000">
    </label>
    <label :for="idPrefix + '-start'">시작 (한국시간, 선택)
      <input :id="idPrefix + '-start'" v-model="task.start" type="datetime-local" step="1" :required="Boolean(task.end)">
    </label>
    <label :for="idPrefix + '-end'">종료 (한국시간, 선택)
      <input :id="idPrefix + '-end'" v-model="task.end" type="datetime-local" step="1" :required="Boolean(task.start)">
    </label>
    <label :for="idPrefix + '-status'">상태
      <select :id="idPrefix + '-status'" v-model="task.status">
        <option v-for="status in ['TODO', 'IN_PROGRESS', 'DONE', 'SKIPPED']" :key="status" :value="status">{{ statuses[status] }}</option>
      </select>
    </label>
  </div>
</template>
