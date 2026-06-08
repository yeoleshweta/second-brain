import type { Attachment, ChatStreamEvent, ChatSessionSummary } from '@/types'

const ACTIVE_SESSION_KEY = 'centralperk_active_session'
/** Stored when user explicitly starts a fresh chat (don't auto-resume latest). */
const NEW_CHAT_SENTINEL = '__new__'

const API_TOKEN = import.meta.env.VITE_API_TOKEN || 'change-me-to-a-long-random-string'

function resolveApiBase(): string {
  const configured = import.meta.env.VITE_API_URL
  if (configured) return configured.replace(/\/$/, '')

  // For localhost development, direct backend avoids proxy SSE quirks.
  // For phone/Tailscale access, prefer same-origin `/api` via Vite proxy to avoid CORS issues.
  const host = window.location.hostname
  const isLocalHost = host === 'localhost' || host === '127.0.0.1'
  if (isLocalHost) {
    return `${window.location.protocol}//${host}:8000`
  }
  return ''
}

const API_BASE = resolveApiBase()

function authHeaders(): HeadersInit {
  return {
    Authorization: `Bearer ${API_TOKEN}`,
  }
}

/**
 * Send a chat message and yield streamed SSE events.
 */
export async function* streamChat(
  message: string,
  attachments: Attachment[] = [],
  chatHistory: { role: string; content: string }[] = [],
  sessionId: string | null = null,
): AsyncGenerator<ChatStreamEvent> {
  const parseEventBlock = (block: string): ChatStreamEvent | null => {
    const lines = block.split(/\r?\n/)
    let eventName: ChatStreamEvent['event'] = 'message'
    const dataLines: string[] = []

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim() as ChatStreamEvent['event']
      } else if (line.startsWith('data:')) {
        // Keep multiline data intact; only strip the single optional prefix space.
        dataLines.push(line.slice(5).replace(/^\s/, ''))
      }
    }

    const data = dataLines.join('\n')
    if (!data && eventName !== 'done') return null
    return { event: eventName, data }
  }

  const resp = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({
      message,
      chat_history: chatHistory,
      session_id: sessionId,
      attachments: attachments.map((a) => ({
        type: 'file',
        file_id: a.fileId,
        media_type: a.mediaType,
        filename: a.name,
      })),
    }),
  })

  if (!resp.ok) {
    const errorBody = (await resp.text().catch(() => '')).trim()
    const extra = errorBody ? ` - ${errorBody}` : ''
    throw new Error(`Chat request failed: ${resp.status}${extra}`)
  }

  if (!resp.body) {
    throw new Error('Chat request failed: empty response body')
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      buffer += decoder.decode()
      break
    }
    buffer += decoder.decode(value, { stream: true })

    // SSE events are separated by double newlines (LF or CRLF).
    const parts = buffer.split(/\r?\n\r?\n/)
    buffer = parts.pop() || ''

    for (const part of parts) {
      const parsed = parseEventBlock(part)
      if (!parsed) continue
      yield parsed
      if (parsed.event === 'done' || parsed.event === 'error') return
    }
  }

  if (buffer.trim()) {
    const parsed = parseEventBlock(buffer)
    if (parsed) yield parsed
  }
}

export function isExplicitNewChat(): boolean {
  try {
    return localStorage.getItem(ACTIVE_SESSION_KEY) === NEW_CHAT_SENTINEL
  } catch {
    return false
  }
}

export function getStoredActiveSessionId(): string | null {
  try {
    const value = localStorage.getItem(ACTIVE_SESSION_KEY)
    if (!value || value === NEW_CHAT_SENTINEL) return null
    return value
  } catch {
    return null
  }
}

export function setStoredActiveSessionId(sessionId: string | null): void {
  try {
    if (sessionId) localStorage.setItem(ACTIVE_SESSION_KEY, sessionId)
    else localStorage.setItem(ACTIVE_SESSION_KEY, NEW_CHAT_SENTINEL)
  } catch {
    /* ignore private browsing */
  }
}

export async function listChatSessions(limit = 30): Promise<ChatSessionSummary[]> {
  const resp = await fetch(`${API_BASE}/api/chat/sessions?limit=${limit}`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`List sessions failed: ${resp.status}`)
  const data = await resp.json()
  return data.sessions as ChatSessionSummary[]
}

export async function getChatSessionMessages(sessionId: string): Promise<{
  session: ChatSessionSummary
  messages: Record<string, unknown>[]
}> {
  const resp = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Load session failed: ${resp.status}`)
  return resp.json()
}

export async function uploadFile(file: File): Promise<Attachment> {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`)
  const data = await resp.json()
  return {
    fileId: data.file_id,
    name: file.name,
    mediaType: data.media_type,
    size: data.size,
  }
}

export async function getPlaidLinkToken(): Promise<string> {
  const resp = await fetch(`${API_BASE}/api/plaid/link-token`, { headers: authHeaders() })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Link token failed: ${resp.status}`)
  }
  const data = await resp.json()
  return data.link_token
}

export interface PlaidLinkedItem {
  item_id: string
  institution_name: string
  linked_at: string
}

export interface PlaidStatus {
  configured: boolean
  encryption_configured: boolean
  linked: boolean
  env: string
  items: PlaidLinkedItem[]
}

export async function getPlaidStatus(): Promise<PlaidStatus> {
  const resp = await fetch(`${API_BASE}/api/plaid/status`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`Plaid status failed: ${resp.status}`)
  return resp.json()
}

export async function plaidExchange(
  publicToken: string,
): Promise<{ ok: boolean; item: PlaidLinkedItem }> {
  const resp = await fetch(`${API_BASE}/api/plaid/exchange`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ public_token: publicToken }),
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Plaid exchange failed: ${resp.status}`)
  }
  return resp.json()
}

export async function unlinkPlaidItem(itemId: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/plaid/items/${encodeURIComponent(itemId)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Plaid unlink failed: ${resp.status}`)
  }
}

// ── Reading list ───────────────────────────────────────────────────────────────

export interface ReadingItem {
  id: number
  url: string | null
  title: string
  summary: string | null
  source: string | null
  kind: 'url' | 'paper' | 'note' | 'pdf' | 'ebook' | 'audiobook'
  tags: string
  status: 'unread' | 'in_progress' | 'read'
  progress: number
  saved_at: string
  finished_at: string | null
  mirror_path: string | null
  content_path: string | null
  has_content: boolean
  content_format: 'markdown' | 'pdf' | null
}

export interface ReadingContent {
  id: number
  title: string
  url: string | null
  format: 'markdown' | 'pdf'
  body?: string
  summary?: string | null
}

export interface ReadingStats {
  total: number
  read: number
  in_progress: number
  unread: number
  percent_done: number
}

export async function getReadingList(
  status = 'unread,in_progress',
): Promise<{ items: ReadingItem[]; stats: ReadingStats }> {
  const resp = await fetch(
    `${API_BASE}/api/reading-list?status=${encodeURIComponent(status)}`,
    { headers: authHeaders() },
  )
  if (!resp.ok) throw new Error(`Reading list failed: ${resp.status}`)
  return resp.json()
}

export async function updateItem(
  id: number,
  patch: { status?: string; progress?: number },
): Promise<ReadingItem> {
  const resp = await fetch(`${API_BASE}/api/reading-list/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(patch),
  })
  if (!resp.ok) throw new Error(`Update item failed: ${resp.status}`)
  return resp.json()
}

export async function deleteItem(id: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/reading-list/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Delete item failed: ${resp.status}`)
}

export async function getReadingContent(id: number): Promise<ReadingContent> {
  const resp = await fetch(`${API_BASE}/api/reading-list/${id}/content`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Load content failed: ${resp.status}`)
  return resp.json()
}

export async function fetchReadingFile(id: number): Promise<Blob> {
  const resp = await fetch(`${API_BASE}/api/reading-list/${id}/file`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Load PDF failed: ${resp.status}`)
  return resp.blob()
}

export async function downloadGutenbergBook(bookId: number): Promise<{ reply: string }> {
  const resp = await fetch(`${API_BASE}/api/reading-list/gutenberg/${bookId}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Book download failed: ${resp.status}`)
  return resp.json()
}

export async function addSuggestionsToReadingList(
  items: {
    url?: string
    title: string
    summary?: string
    source?: string
    kind?: string
    tags?: string
    pdf_url?: string
  }[],
): Promise<{ added: number; duplicate: number; items: ReadingItem[] }> {
  const resp = await fetch(`${API_BASE}/api/reading-list/add-suggestions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ items, fetch_content: true }),
  })
  if (!resp.ok) throw new Error(`Add suggestions failed: ${resp.status}`)
  return resp.json()
}

export async function saveItemDirect(item: {
  url?: string
  title: string
  summary?: string
  source?: string
  kind?: string
  tags?: string
}): Promise<{ saved: boolean; duplicate: boolean }> {
  const resp = await fetch(`${API_BASE}/api/reading-list`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(item),
  })
  if (!resp.ok) throw new Error(`Save failed: ${resp.status}`)
  return resp.json()
}

export async function getMorningBriefLatest(): Promise<{
  date: string
  path: string | null
  content: string | null
}> {
  const resp = await fetch(`${API_BASE}/api/morning-brief/latest`, {
    headers: authHeaders(),
  })
  if (!resp.ok) return { date: '', path: null, content: null }
  return resp.json()
}

export interface RossSettings {
  daily_reading_minutes_goal: string
  daily_practice_minutes_goal: string
  active_skills: string
  quiet_hours_start: string
  quiet_hours_end: string
  nudges_paused_until: string
  nudge_morning_brief: string
  nudge_mid_day_reading: string
  nudge_evening_reading: string
  nudge_evening_practice: string
  nudge_weekly_review: string
  nudge_discovery: string
}

export async function getRossSettings(): Promise<RossSettings> {
  const resp = await fetch(`${API_BASE}/api/settings`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`Settings failed: ${resp.status}`)
  return resp.json()
}

export async function patchRossSettings(
  patch: Partial<{
    daily_reading_minutes_goal: number
    daily_practice_minutes_goal: number
    active_skills: string[]
    quiet_hours_start: string
    quiet_hours_end: string
    nudge_morning_brief: boolean
    nudge_mid_day_reading: boolean
    nudge_evening_reading: boolean
    nudge_evening_practice: boolean
    nudge_weekly_review: boolean
    nudge_discovery: boolean
  }>,
): Promise<RossSettings> {
  const resp = await fetch(`${API_BASE}/api/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(patch),
  })
  if (!resp.ok) throw new Error(`Settings update failed: ${resp.status}`)
  return resp.json()
}

export async function getTodayUsage(): Promise<{
  date: string
  estimated_cost_usd: number
  total_tokens: number
}> {
  const resp = await fetch(`${API_BASE}/api/usage/today`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`Usage failed: ${resp.status}`)
  return resp.json()
}

export interface AgendaEvent {
  id: string
  summary: string
  start: string
  time_label: string
  attendees: string[]
  prep_note?: string | null
}

export interface ChandlerAgendaResponse {
  reply: string
  events: AgendaEvent[]
  connected?: boolean
  scope?: string
  error?: string
}

export async function fetchChandlerAgenda(scope: 'today' | 'week' = 'today'): Promise<ChandlerAgendaResponse> {
  const resp = await fetch(`${API_BASE}/api/chandler/agenda?scope=${scope}`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`Agenda failed: ${resp.status}`)
  return resp.json()
}
