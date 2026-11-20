<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TaskFields from '../components/TaskFields.vue'
import { api, conversation, session } from '../state.js'
import { errorMessage } from '../api.js'
import { rules, statuses, taskEditor, taskPayload, timestamp } from '../format.js'

const route = useRoute()
const router = useRouter()
const collection = ref({ items: [], total: 0 })
const offset = ref(0)
const limit = 10
const listLoading = ref(false)
const listError = ref('')
const detail = ref(null)
const activeId = ref(null)
const detailLoading = ref(false)
const busy = ref(false)
const error = ref('')
const conflict = ref(false)
const editing = ref(null)
const titleEdit = ref(null)
const deletingPlan = ref(false)
const form = ref(null)
const taskTitles = computed(() => Object.fromEntries([
  ...collection.value.items.flatMap((plan) => plan.tasks), ...(detail.value?.tasks ?? []),
].map((task) => [task.id, task.title])))
let listVersion = 0
let detailVersion = 0

async function loadList() {
  const version = ++listVersion
  if (session.status !== 'active') return
  listLoading.value = true
  listError.value = ''
  try {
    const result = await api.request(`/plans?limit=${limit}&offset=${offset.value}`)
    if (version === listVersion) collection.value = result
  } catch (failure) {
    if (version === listVersion) listError.value = errorMessage(failure)
  } finally {
    if (version === listVersion) listLoading.value = false
  }
}

async function selectPlan(id) {
  const version = ++detailVersion
  activeId.value = id
  form.value = null
  detail.value = null
  error.value = ''
  conflict.value = false
  editing.value = titleEdit.value = null
  deletingPlan.value = false
  detailLoading.value = true
  try {
    const plan = await api.request('/plans/' + id)
    if (version === detailVersion) detail.value = plan
  } catch (failure) {
    if (version === detailVersion) error.value = errorMessage(failure)
  } finally {
    if (version === detailVersion) detailLoading.value = false
  }
}

function openForm(draft = null) {
  ++detailVersion
  detailLoading.value = false
  detail.value = activeId.value = null
  error.value = ''
  conflict.value = false
  deletingPlan.value = false
  form.value = {
    title: draft?.title ?? '', planning_start_date: draft?.planning_start_date ?? '',
    planning_end_date: draft?.planning_end_date ?? '', constraints: draft?.constraints ?? {},
    source_refs: draft?.source_refs, runId: draft?.runId, tasks: (draft?.tasks ?? []).map(taskEditor),
  }
}

watch(() => [session.status, session.epoch], () => {
  ++listVersion
  ++detailVersion
  collection.value = { items: [], total: 0 }
  detail.value = activeId.value = form.value = editing.value = titleEdit.value = null
  listLoading.value = detailLoading.value = busy.value = conflict.value = deletingPlan.value = false
  listError.value = error.value = ''
  offset.value = 0
  if (session.status === 'active') loadList()
}, { immediate: true })

watch(() => route.query.draft, (flag) => {
  if (flag && conversation.draft && !conversation.draftSaved) openForm(conversation.draft)
}, { immediate: true })

function changePage(delta) {
  offset.value += delta
  loadList()
}

async function action(fn) {
  if (busy.value || session.status !== 'active') return
  const epoch = session.epoch
  const current = () => epoch === session.epoch
  busy.value = true
  error.value = ''
  try { await fn(current) }
  catch (failure) {
    if (current()) {
      error.value = errorMessage(failure)
      conflict.value = failure.status === 409
    }
  } finally {
    if (current()) busy.value = false
  }
}

function save() {
  return action(async (current) => {
    const value = form.value
    const body = {
      title: value.title, category: 'FIRST_JOB_INDEPENDENCE', planning_start_date: value.planning_start_date,
      planning_end_date: value.planning_end_date, constraints: value.constraints,
      tasks: value.tasks.map(taskPayload),
      ...(value.runId ? { generated_by_run_id: value.runId, source_refs: value.source_refs } : {}),
    }
    const plan = await api.request('/plans', { method: 'POST', body })
    if (!current()) return
    if (value.runId && value.runId === conversation.draft?.runId) conversation.draftSaved = true
    form.value = null
    detail.value = plan
    activeId.value = plan.id
    if (route.query.draft) router.replace('/plans')
    offset.value = 0
    await loadList()
  })
}

function patch(changes) {
  return action(async (current) => {
    const plan = detail.value
    const result = await api.request('/plans/' + plan.id, {
      method: 'PATCH', body: { expected_revision_number: plan.revision_number, ...changes },
    })
    if (!current()) return
    detail.value = result
    editing.value = titleEdit.value = null
    conflict.value = false
    await loadList()
  })
}

function startEdit(task = null) {
  editing.value = { id: task?.id, task: taskEditor(task ?? { task_date: detail.value.planning_start_date }) }
}

function updateTask() {
  const { id, task } = editing.value
  const op = id ? { op: 'update', task_id: id, changes: taskPayload(task) } : { op: 'add', task: taskPayload(task) }
  return patch({ tasks: [op] })
}

function removePlan() {
  return action(async (current) => {
    await api.request('/plans/' + detail.value.id, { method: 'DELETE' })
    if (!current()) return
    detail.value = activeId.value = null
    deletingPlan.value = false
    if (offset.value && collection.value.items.length === 1) offset.value -= limit
    await loadList()
  })
}
</script>

<template>
  <header class="page-header"><h1>내 계획</h1><button class="primary" :disabled="busy || session.status !== 'active'" @click="openForm()">새 계획</button></header>
  <div class="management">
    <section class="panel list-panel">
      <div class="panel-heading"><h2>저장한 계획</h2><small>{{ collection.total }}개</small></div>
      <p v-if="listLoading" role="status" class="loading">목록을 불러오는 중입니다.</p>
      <div v-else-if="listError" role="alert" class="error-box">{{ listError }} <button @click="loadList">다시 불러오기</button></div>
      <p v-else-if="!collection.items.length" class="empty">아직 저장한 계획이 없습니다.</p>
      <ul v-else class="selection-list">
        <li v-for="plan in collection.items" :key="plan.id">
          <button :disabled="busy" :aria-pressed="activeId === plan.id" @click="selectPlan(plan.id)">
            <strong>{{ plan.title }}</strong><small>{{ plan.planning_start_date }} ~ {{ plan.planning_end_date }}</small>
          </button>
        </li>
      </ul>
      <div v-if="collection.total > limit" class="actions">
        <button :disabled="offset === 0 || listLoading || busy" @click="changePage(-limit)">이전</button>
        <button :disabled="offset + limit >= collection.total || listLoading || busy" @click="changePage(limit)">다음</button>
      </div>
    </section>

    <section class="panel detail-panel">
      <div v-if="error" class="error-box" role="alert">{{ error }}
        <button v-if="conflict && activeId" @click="selectPlan(activeId)">최신 계획 불러오기</button>
      </div>
      <p v-if="detailLoading || busy" class="loading" role="status">요청을 처리하고 있습니다.</p>

      <form v-if="form" class="stack" @submit.prevent="save">
        <h2>{{ form.runId ? '계획 초안 저장' : '계획 만들기' }}</h2>
        <div class="form-grid">
          <label class="wide">계획 이름 <input v-model.trim="form.title" required maxlength="160"></label>
          <label>계획 시작일 <input v-model="form.planning_start_date" type="date" required></label>
          <label>계획 종료일 <input v-model="form.planning_end_date" :min="form.planning_start_date" type="date" required></label>
        </div>
        <fieldset v-for="(task, index) in form.tasks" :key="index">
          <legend>작업 {{ index + 1 }}</legend>
          <TaskFields :task="task" :id-prefix="'draft-task-' + index" />
          <button type="button" :disabled="busy" @click="form.tasks.splice(index, 1)">작업 제거</button>
        </fieldset>
        <div class="actions">
          <button type="button" :disabled="busy || form.tasks.length >= 100" @click="form.tasks.push(taskEditor())">작업 추가</button>
          <button class="primary" :disabled="busy || session.status !== 'active'">계획 저장</button>
        </div>
      </form>

      <template v-else-if="detail">
        <div class="detail-heading">
          <div><h2>{{ detail.title }}</h2><p class="muted">{{ detail.planning_start_date }} ~ {{ detail.planning_end_date }} · 버전 {{ detail.revision_number }}</p></div>
          <RouterLink :to="{ path: '/', query: { plan: detail.id } }">계획 이어서 상담</RouterLink>
        </div>
        <div v-if="detail.warnings.length" class="warning-box" role="status">
          <strong>겹치는 일정 {{ detail.warnings.length }}건</strong>
          <p>계획은 저장되어 있습니다. 아래 일정의 시간을 확인해 주세요.</p>
          <ul><li v-for="warning in detail.warnings" :key="warning.task_id + warning.conflicting_task_id">
            {{ taskTitles[warning.task_id] ?? '이 계획의 작업' }} · {{ taskTitles[warning.conflicting_task_id] ?? '다른 계획의 작업' }}
          </li></ul>
        </div>
        <form v-if="titleEdit !== null" class="actions" @submit.prevent="patch({ title: titleEdit })">
          <label>새 계획 이름 <input v-model.trim="titleEdit" required maxlength="160"></label>
          <button class="primary" :disabled="busy || conflict">이름 저장</button><button type="button" @click="titleEdit = null">취소</button>
        </form>
        <div v-else class="actions">
          <button :disabled="busy || conflict" @click="titleEdit = detail.title">이름 수정</button>
          <button class="danger" :disabled="busy" @click="deletingPlan = true">계획 삭제</button>
        </div>
        <div v-if="deletingPlan" class="warning-box">
          <p>이 계획과 작업을 삭제할까요?</p>
          <div class="actions"><button class="danger" :disabled="busy" @click="removePlan">삭제 확인</button><button @click="deletingPlan = false">취소</button></div>
        </div>

        <div class="panel-heading tasks-heading"><h3>작업</h3><button :disabled="busy || conflict" @click="startEdit()">작업 추가</button></div>
        <p v-if="!detail.tasks.length" class="empty">아직 작업이 없습니다.</p>
        <ul v-else class="task-list">
          <li v-for="task in detail.tasks" :key="task.id">
            <div><strong>{{ task.title }}</strong> <span class="chip">{{ statuses[task.status] }}</span>
              <p>{{ task.scheduled_start_at ? timestamp(task.scheduled_start_at) + ' ~ ' + timestamp(task.scheduled_end_at) : task.task_date + ' · 시간 미정' }}</p>
              <p v-if="task.description">{{ task.description }}</p>
            </div>
            <div class="actions"><button :disabled="busy || conflict" @click="startEdit(task)">작업 수정</button>
              <button class="danger" :disabled="busy || conflict" @click="patch({ tasks: [{ op: 'delete', task_id: task.id }] })">작업 삭제</button></div>
          </li>
        </ul>
        <form v-if="editing" class="stack task-edit" @submit.prevent="updateTask">
          <h3>{{ editing.id ? '작업 수정' : '작업 추가' }}</h3>
          <TaskFields :task="editing.task" id-prefix="edit-task" />
          <div class="actions"><button class="primary" :disabled="busy || conflict">작업 저장</button><button type="button" @click="editing = null">취소</button></div>
        </form>
        <section v-if="detail.sources.length || detail.evaluations.length" class="plan-evidence">
          <h3>출처와 판정</h3>
          <ul><li v-for="source in detail.sources" :key="source.id">
            <a v-if="source.source_url?.startsWith('https://')" :href="source.source_url" target="_blank" rel="noopener noreferrer">{{ source.provider }}</a>
            <span v-else>{{ source.provider }}</span> <small v-if="source.caveat"> · {{ source.caveat }}</small>
          </li></ul>
          <ul class="checks"><li v-for="item in detail.evaluations" :key="item.id">
            <span>{{ rules[item.rule_code] ?? item.rule_code }}</span>
            <span :class="['chip', item.status.toLowerCase()]">{{ item.status === 'UNKNOWN' ? 'UNKNOWN' : statuses[item.status] }}</span>
          </li></ul>
        </section>
      </template>
      <p v-else-if="!detailLoading && !error" class="empty">왼쪽 목록에서 계획을 선택하거나 새 계획을 만들어 주세요.</p>
    </section>
  </div>
</template>
