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
  const resp = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: {
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

  if (!resp.ok || !resp.body) {
    throw new Error(`Chat request failed: ${resp.status}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE events are separated by double newlines
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const lines = part.split('\n')
      let eventName = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (data) {
        yield { event: eventName as ChatStreamEvent['event'], data }
        if (eventName === 'done' || eventName === 'error') return
      }
    }
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
