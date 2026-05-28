import type { Attachment, ChatStreamEvent } from '@/types'

// In production you'd load this from a setting. For local dev the proxy handles it.
const API_TOKEN = import.meta.env.VITE_API_TOKEN || 'change-me-to-a-long-random-string'

// If VITE_API_URL is set, hit the backend directly (bypasses Vite's proxy, which
// doesn't reliably stream SSE responses). Empty/unset = relative URLs via proxy.
const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

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
