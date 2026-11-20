const koreanTime = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul', dateStyle: 'medium', timeStyle: 'short',
})

export const timestamp = (value) => value ? koreanTime.format(new Date(value)) : '미정'
export const duration = (value) => value == null ? '—' : value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(2)}초`

export const statuses = {
  SUCCEEDED: '완료', PARTIAL: '일부 확인', NEEDS_INPUT: '입력 필요', FAILED: '실패', RUNNING: '진행 중',
  EXHAUSTED: '탐색 종료', PASS: '충족', FAIL: '미충족', UNKNOWN: '미확인', SKIPPED: '건너뜀',
  TODO: '할 일', IN_PROGRESS: '진행 중', DONE: '완료',
}
export const rules = {
  PLAN_TIMELINE: '준비 일정', HISTORICAL_DEPOSIT: '과거 보증금', HISTORICAL_RENT: '과거 월세',
  CURRENT_LISTING: '현재 매물 여부', BUILDING_MATCH: '건물 일치', MAINTENANCE_FEE: '관리비', COMMUTE_TIME: '통근시간',
}
export const tools = {
  search_location: '지역 및 주소 검색', search_rental_transactions: '과거 전월세 조회', get_building_detail: '건축물대장 확인',
}
export const events = {
  RUN_STARTED: 'Agent 실행 시작', NODE_STARTED: '단계 시작', NODE_FINISHED: '단계 완료',
  INTENT_DECIDED: '요청 의도 분석', WORKFLOW_CREATED: '조회 계획 수립', TOOL_REQUESTED: '도구 호출',
  TOOL_SUCCEEDED: '도구 성공', TOOL_FAILED: '도구 실패', CONSTRAINT_EVALUATED: '조건 검증',
  REPLAN_STARTED: '재계획 시작', REPLAN_EXHAUSTED: '재계획 종료', RUN_FINISHED: 'Agent 실행 완료', RUN_FAILED: 'Agent 실행 실패',
}
export const nodes = {
  analyze_request: '요청 분석', validate_input: '입력 검증', plan_workflow: '조회 계획',
  execute_tools: '도구 실행', normalize_results: '결과 정리', evaluate_constraints: '조건 검증',
  replan: '재계획', generate_response: '응답 작성',
}

export function kstInput(value) {
  return value ? new Date(new Date(value).getTime() + 9 * 3600000).toISOString().slice(0, 19) : ''
}

export function kstTimestamp(value) {
  return value ? value + '+09:00' : null
}

export function taskPayload(task) {
  return {
    title: task.title, description: task.description || null, task_date: task.task_date,
    scheduled_start_at: kstTimestamp(task.start), scheduled_end_at: kstTimestamp(task.end), status: task.status,
    ...(task.estimated_cost_krw == null ? {} : { estimated_cost_krw: task.estimated_cost_krw }),
    ...(task.estimated_duration_minutes == null ? {} : { estimated_duration_minutes: task.estimated_duration_minutes }),
  }
}

export function taskEditor(task = {}) {
  return {
    title: task.title ?? '', description: task.description ?? '', task_date: task.task_date ?? '',
    start: kstInput(task.scheduled_start_at), end: kstInput(task.scheduled_end_at), status: task.status ?? 'TODO',
    estimated_cost_krw: task.estimated_cost_krw, estimated_duration_minutes: task.estimated_duration_minutes,
  }
}
