import { reactive, watch } from 'vue'
import { createApi } from './api.js'

export const session = reactive({ status: 'new', epoch: 0, starting: false })
export const api = createApi(window.sessionStorage, session)
export const conversation = reactive({ entries: [], pending: false, draft: null, draftSaved: false, runId: null })

watch(() => session.epoch, () => {
  Object.assign(conversation, { entries: [], pending: false, draft: null, draftSaved: false, runId: null })
}, { flush: 'sync' })
