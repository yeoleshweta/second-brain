import type { Attachment, ChatStreamEvent } from '@/types'

const API_TOKEN = import.meta.env.VITE_API_TOKEN || 'change-me-to-a-long-random-string'

// Dynamic API base: when accessed from a phone over Tailscale, window.location.hostname
// is the Mac's MagicDNS name, so this automatically points to the right backend.
const API_BASE = (
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`
).replace(/\/$/, '')

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
      attachments: attachments.map((a) => ({
        type: 'file',
        file_id: a.fileId,
        media_type: a.mediaType,
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
  if (!resp.ok) throw new Error(`Link token failed: ${resp.status}`)
  const data = await resp.json()
  return data.link_token
}

export async function plaidExchange(publicToken: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/plaid/exchange`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ public_token: publicToken }),
  })
  if (!resp.ok) throw new Error(`Plaid exchange failed: ${resp.status}`)
}

// ── Reading list ───────────────────────────────────────────────────────────────

export interface ReadingItem {
  id: number
  url: string | null
  title: string
  summary: string | null
  source: string | null
  kind: 'url' | 'paper' | 'note'
  tags: string
  status: 'unread' | 'in_progress' | 'read'
  progress: number
  saved_at: string
  finished_at: string | null
  mirror_path: string | null
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
