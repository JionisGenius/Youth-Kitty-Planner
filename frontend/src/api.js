const storageKey = 'ykp-session'
const runPattern = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i

export class ApiError extends Error {
  constructor(status, code, runId = null) {
    super('API request failed')
    this.status = status
    this.code = code
    this.runId = typeof runId === 'string' && runPattern.test(runId) ? runId : null
  }
}

export function errorMessage(error) {
  if (error.code === 'SESSION_CHANGED') return '세션이 바뀌었습니다. 다시 시도해 주세요.'
  if (error.status === 401) return '세션이 만료되었습니다. 새 세션을 시작해 주세요.'
  if (error.status === 429 || error.code === 'RATE_LIMITED') return 'AI 서비스 호출 한도에 도달했습니다. 잠시 후 직접 다시 시도해 주세요.'
  if (error.code === 'AUTH_FAILED') return '서버의 AI 또는 외부 API 키 설정을 확인해 주세요.'
  if (error.status === 409) return '다른 곳에서 계획이 수정되었습니다. 최신 버전을 불러온 후 다시 편집해 주세요.'
  if (error.status === 404) return '이 세션에서 해당 기록을 찾을 수 없습니다.'
  if (error.status === 422) return '필수 값과 날짜·시간 입력을 확인해 주세요.'
  return '요청을 완료하지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요.'
}

export function createApi(storage, session, fetcher = fetch, now = Date.now) {
  let credential = null
  try {
    const saved = JSON.parse(storage.getItem(storageKey))
    if (typeof saved?.access_token === 'string' && Number.isFinite(Date.parse(saved.expires_at))) {
      if (Date.parse(saved.expires_at) > now()) {
        credential = saved
        session.status = 'active'
      } else {
        session.status = 'expired'
        storage.removeItem(storageKey)
      }
    }
  } catch {
    // Unsupported or invalid browser storage can still use an in-memory session.
  }

  function expire() {
    if (session.status === 'expired') return
    credential = null
    try { storage.removeItem(storageKey) } catch { /* storage unavailable */ }
    session.status = 'expired'
    session.epoch++
  }

  function checkSession() {
    if (credential && Date.parse(credential.expires_at) <= now()) expire()
  }

  async function request(path, { method = 'GET', body, authenticated = true } = {}) {
    if (authenticated && (session.status !== 'active' || !credential || Date.parse(credential.expires_at) <= now())) {
      expire()
      throw new ApiError(401, 'UNAUTHORIZED')
    }
    const epoch = session.epoch
    const headers = { Accept: 'application/json' }
    if (authenticated) headers.Authorization = 'Bearer ' + credential.access_token
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    let response
    try {
      response = await fetcher('/api/v1' + path, {
        method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: 'no-store',
      })
    } catch {
      throw new ApiError(0, 'NETWORK_ERROR')
    }
    if (response.status === 204 && epoch === session.epoch) return null
    const data = await response.json().catch(() => null)
    if (epoch !== session.epoch) throw new ApiError(0, 'SESSION_CHANGED')
    if (!response.ok) {
      if (response.status === 401 && authenticated) expire()
      const code = ['RATE_LIMITED', 'AUTH_FAILED'].includes(data?.error?.code) ? data.error.code : 'HTTP_ERROR'
      throw new ApiError(response.status, code, data?.error?.details?.run_id)
    }
    if (data === null) throw new ApiError(0, 'INVALID_RESPONSE')
    return data
  }

  async function startSession() {
    if (session.starting) return
    session.starting = true
    try {
      const next = await request('/sessions', { method: 'POST', authenticated: false })
      if (!next.access_token || !Number.isFinite(Date.parse(next.expires_at))) {
        throw new ApiError(0, 'INVALID_RESPONSE')
      }
      credential = next
      try { storage.setItem(storageKey, JSON.stringify(next)) } catch { /* storage unavailable */ }
      session.epoch++
      session.status = 'active'
    } finally {
      session.starting = false
    }
  }

  return { request, startSession, checkSession }
}
