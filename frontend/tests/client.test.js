import assert from 'node:assert/strict'
import test from 'node:test'
import { createApi, errorMessage } from '../src/api.js'
import { groupPlanSources, kstInput, taskEditor, taskPayload, taskTimeRange } from '../src/format.js'

test('shows both KST dates for a task spanning multiple days', () => {
  assert.equal(taskTimeRange('2026-11-20T07:51:40Z', '2026-11-27T07:51:44Z'),
    '2026년 11월 20일 16:51 ~ 2026년 11월 27일 16:51 KST')
  assert.equal(taskTimeRange('2026-11-20T07:51:40Z', '2026-11-20T08:51:44Z'), '16:51 ~ 17:51 KST')
  assert.equal(taskTimeRange(null, null), '시간 미정')
})

test('groups repeated official source links and preserves counts and distinct caveats', () => {
  const rent = { provider: 'MOLIT_RENT', source_type: 'OFFICIAL_API', source_url: 'https://example.test/rent', caveat: '과거 거래' }
  const groups = groupPlanSources([
    { ...rent, id: '1' }, { ...rent, id: '2' }, { ...rent, id: '3', caveat: '현재 임대 여부 미확인' },
    { ...rent, id: '4', source_url: 'https://example.test/other' },
    { ...rent, id: '5', provider: 'BUILDING_HUB' },
  ])
  assert.deepEqual(groups.map(group => [group.id, group.count, [...group.caveats]]), [
    ['1', 3, ['과거 거래', '현재 임대 여부 미확인']], ['4', 1, ['과거 거래']], ['5', 1, ['과거 거래']],
  ])
})

function fixture(fetcher, clock = () => 0) {
  const values = new Map()
  const storage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key) }
  const session = { status: 'new', epoch: 0, starting: false }
  const api = createApi(storage, session, fetcher, clock)
  return { api, session, values }
}

const created = () => Response.json({ access_token: 'synthetic', expires_at: '2026-11-20T06:00:00Z' })

test('creates a session without auth then attaches Bearer only to protected calls', async () => {
  const requests = []
  const { api, session } = fixture(async (url, options) => {
    requests.push([url, options])
    return url.endsWith('/sessions') ? created() : Response.json({ items: [] })
  })
  await api.startSession()
  await api.request('/plans')
  assert.equal(session.status, 'active')
  assert.equal(requests[0][1].headers.Authorization, undefined)
  assert.equal(requests[1][1].headers.Authorization, 'Bearer synthetic')
})

test('maps backend 502 with RATE_LIMITED to a safe message and does not retry', async () => {
  let calls = 0
  const runId = '14893e6a-1143-4791-a731-15aa22856af2'
  const { api, session } = fixture(async (url) => {
    if (url.endsWith('/sessions')) return created()
    calls++
    return Response.json({ error: { code: 'RATE_LIMITED', message: 'private upstream', details: { run_id: runId } } }, { status: 502 })
  })
  await api.startSession()
  await assert.rejects(api.request('/chat', { method: 'POST' }), (error) => {
    assert.equal(error.runId, runId)
    assert.match(errorMessage(error), /AI 서비스 호출 한도/)
    assert.doesNotMatch(errorMessage(error), /private upstream/)
    return true
  })
  assert.equal(calls, 1)
  assert.equal(session.status, 'active')
})

test('clears expired auth on local expiry and upstream 401, then re-authenticates explicitly', async () => {
  let now = 0
  let calls = 0
  const { api, session, values } = fixture(async (url) => {
    if (url.endsWith('/sessions')) return created()
    calls++
    return Response.json({}, { status: 401 })
  }, () => now)
  await api.startSession()
  now = Date.parse('2026-11-20T06:01:00Z')
  api.checkSession()
  assert.equal(session.status, 'expired')
  assert.equal(values.size, 0)
  await assert.rejects(api.request('/plans'), { status: 401 })
  assert.equal(calls, 0)
  now = 0
  await api.startSession()
  await assert.rejects(api.request('/logs'), { status: 401 })
  assert.equal(session.status, 'expired')
  assert.equal(calls, 1)
  assert.equal(values.size, 0)
})

test('returns an actionable conflict without leaking the raw server message', async () => {
  const { api } = fixture(async (url) => url.endsWith('/sessions') ? created()
    : Response.json({ error: { message: 'raw failure detail' } }, { status: 409 }))
  await api.startSession()
  await assert.rejects(api.request('/plans/synthetic', { method: 'PATCH' }), (error) => {
    assert.equal(error.status, 409)
    assert.match(errorMessage(error), /최신 버전/)
    assert.doesNotMatch(errorMessage(error), /raw failure detail/)
    return true
  })
})

test('renders KST editing times and preserves unspecified schedule as null', () => {
  const empty = taskEditor({ title: '작업', task_date: '2026-11-20' })
  assert.equal(taskPayload(empty).scheduled_start_at, null)
  assert.equal(taskPayload(empty).scheduled_end_at, null)
  assert.equal(kstInput('2026-11-20T01:30:00Z'), '2026-11-20T10:30:00')
  assert.equal(taskPayload({ ...empty, start: '2026-11-20T10:30' }).scheduled_start_at, '2026-11-20T10:30+09:00')
})


test('separates missing provider keys from a user session 401', async () => {
  const { api, session } = fixture(async (url) => url.endsWith('/sessions') ? created()
    : Response.json({ error: { code: 'AUTH_FAILED', message: 'credential detail' } }, { status: 502 }))
  await api.startSession()
  await assert.rejects(api.request('/chat', { method: 'POST' }), (error) => {
    assert.match(errorMessage(error), /API 키 설정/)
    assert.doesNotMatch(errorMessage(error), /credential detail/)
    return true
  })
  assert.equal(session.status, 'active')
})
