const koreanTime = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul', dateStyle: 'medium', timeStyle: 'short',
})

export const timestamp = (value) => value ? koreanTime.format(new Date(value)) : '미정'
export const duration = (value) => value == null ? '—' : value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(2)}초`
const number = new Intl.NumberFormat('ko-KR')
export const money = (value) => value == null ? '미정' : `${number.format(value)}원`
export function evaluationValue(rule, value) {
  if (value == null) return '미확인'
  if (['HISTORICAL_RENT', 'HISTORICAL_DEPOSIT', 'MAINTENANCE_FEE'].includes(rule)) return money(value)
  return rule === 'COMMUTE_TIME' ? `${value}분` : value
}
const day = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: 'long', day: 'numeric', weekday: 'short' })
const clock = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
export const dayLabel = (value) => day.format(new Date(value))
export const clockTime = (value) => clock.format(new Date(value))

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
export const providers = {
  MOLIT_RENT: '국토교통부 전월세 실거래', KAKAO_LOCAL: '카카오 로컬', BUILDING_HUB: '건축HUB 건축물대장',
}
export const intents = {
  CREATE_PLAN: '독립 준비 계획', UPDATE_CONSTRAINT: '조건 변경', FACT_QUERY: '자료 조회',
  EXPLAIN_PLAN: '계획 설명', GENERAL: '일반 대화',
}
export const events = {
  RUN_STARTED: 'AI가 요청을 받았어요', NODE_STARTED: '단계 시작', NODE_FINISHED: '단계 완료',
  INTENT_DECIDED: '요청 내용 파악', WORKFLOW_CREATED: '자료 조회 순서 결정', TOOL_REQUESTED: '자료 조회 요청',
  TOOL_SUCCEEDED: '자료 조회 성공', TOOL_FAILED: '자료 조회 실패', CONSTRAINT_EVALUATED: '예산·일정 조건 확인',
  REPLAN_STARTED: '새 대안 탐색 시작', REPLAN_EXHAUSTED: '대안 탐색 종료', RUN_FINISHED: '답변 작성 완료', RUN_FAILED: '실행을 완료하지 못했어요',
}
export const anomalyFindings = {
  DUPLICATE_TOOL_CALL: '같은 자료를 같은 조건으로 반복 조회',
  REPLAN_LIMIT_EXCEEDED: '대안 탐색 횟수 초과',
  UNPLANNED_TOOL: '계획에 없던 자료 조회',
  WORKFLOW_EXECUTION_MISMATCH: '계획과 실행 기록 불일치',
}
export const anomalyCauses = {
  EXECUTION_DEDUPLICATION: '중복 실행 제어', REPLAN_CONTROL: '대안 탐색 횟수 제어',
  WORKFLOW_DISPATCH: '작업 순서 및 배정', INSUFFICIENT_CONTEXT: '원인 추정에 필요한 정보 부족',
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
