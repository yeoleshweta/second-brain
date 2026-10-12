import type { IncomingMessage, ServerResponse } from 'http'
import { isAuthorized } from './auth.js'
import { blobConfigured } from './blob.js'
import { claudeHealth, completeClaude, probeClaude, publicClaudeError } from './claude.js'
import { formatInZone, zoneNow } from './capture.js'
import { calendarReply, skipsVault } from './calendar.js'
import { loadState, saveState, sessionToApi, titleFromMessage, type AppState, type StoredSession } from './store.js'
import * as wiki from './wiki.js'

type VercelReq = IncomingMessage & {
  method?: string
  query: Record<string, string | string[] | undefined>
  body?: unknown
}

function asSegments(raw: string | string[] | undefined): string[] {
  if (Array.isArray(raw)) return raw.filter(Boolean)
  if (typeof raw === 'string' && raw) return raw.split('/').filter(Boolean)
  return []
}

function routeParts(req: VercelReq): string[] {
  const pathname = (req.url || '').split('?')[0] || ''
  const fromUrl = pathname.replace(/^\/api\/?/, '').split('/').filter(Boolean)
  const fromQuery = [
    ...asSegments(req.query?.path),
    ...asSegments(req.query?.slug),
  ]
  const candidates = [fromUrl, fromQuery].filter((c) => c.length)
  candidates.sort((a, b) => b.length - a.length)
  return candidates[0] || []
}

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify(body))
}

function sseWrite(res: ServerResponse, event: string, data: string): void {
  res.write(`event: ${event}\ndata: ${data.replace(/\n/g, '\ndata: ')}\n\n`)
}

function openaiKey(): string {
  return (process.env.OPENAI_API_KEY || '').trim()
}

function keyHealth() {
  const key = openaiKey()
  return {
    openai_key_present: Boolean(key),
    openai_key_format_ok: key.startsWith('sk-') && key.length > 20,
  }
}

async function probeOpenAi(): Promise<{ ok: boolean; code: string }> {
  const key = openaiKey()
  if (!key) return { ok: false, code: 'missing' }
  if (!keyHealth().openai_key_format_ok) return { ok: false, code: 'malformed' }
  try {
    const resp = await fetch('https://api.openai.com/v1/models', {
      headers: { Authorization: `Bearer ${key}` },
    })
    if (resp.status === 401) return { ok: false, code: 'invalid_api_key' }
    if (resp.status === 429) return { ok: false, code: 'rate_limit_or_quota' }
    if (!resp.ok) return { ok: false, code: `http_${resp.status}` }
    return { ok: true, code: 'ok' }
  } catch {
    return { ok: false, code: 'unreachable' }
  }
}

function parseBody(req: VercelReq): Record<string, unknown> {
  const body = req.body
  if (body && typeof body === 'object' && !Buffer.isBuffer(body)) {
    return body as Record<string, unknown>
  }
  if (typeof body === 'string') {
    try {
      return JSON.parse(body) as Record<string, unknown>
    } catch {
      return {}
    }
  }
  return {}
}

const CHAT_SYSTEM = `You are the user's Second Brain. Answer helpfully and concisely.
Knowledge capture goes to Inbox and waits for Review. Do not claim you already filed a permanent note.
Do not dump meetings or emails into the wiki. Calendar adds happen only after an explicit confirm in the Mac app.`

async function chatCompletion(userMessage: string, history: { role: string; content: string }[]): Promise<string> {
  try {
    return (
      (await completeClaude({
        system: CHAT_SYSTEM,
        user: userMessage,
        messages: history.slice(-8),
        maxTokens: 1024,
      })) || "I'm here. What's on your mind?"
    )
  } catch (err) {
    return publicClaudeError(err)
  }
}

async function handleChat(req: VercelReq, res: ServerResponse): Promise<void> {
  const body = parseBody(req)
  const message = String(body.message || '')
  const sessionIdIn = typeof body.session_id === 'string' ? body.session_id : null
  const historyIn = Array.isArray(body.chat_history)
    ? (body.chat_history as { role: string; content: string }[])
    : []

  res.statusCode = 200
  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8')
  res.setHeader('Cache-Control', 'no-cache, no-transform')
  res.setHeader('Connection', 'keep-alive')

  let state: AppState
  try {
    state = blobConfigured() ? await loadState() : { sessions: [], settings: {} }
  } catch {
    state = { sessions: [], settings: {} }
  }

  let session: StoredSession | undefined = sessionIdIn
    ? state.sessions.find((s) => s.id === sessionIdIn)
    : undefined
  const nowIso = new Date().toISOString()
  if (!session) {
    session = {
      id: crypto.randomUUID(),
      title: titleFromMessage(message),
      created_at: nowIso,
      updated_at: nowIso,
      messages: [],
    }
    state.sessions.unshift(session)
  }

  sseWrite(res, 'session_id', session.id)
  sseWrite(res, 'status', 'thinking')

  const dbHistory = session.messages.slice(-20).map((m) => ({ role: m.role, content: m.content }))
  const history = dbHistory.length ? dbHistory : historyIn

  try {
    const calendar = calendarReply(message)
    const reply = calendar || (await chatCompletion(message, history))
    let obsidianPath: string | null = null
    let finalReply = reply
    const skipInbox = Boolean(calendar) || skipsVault(message)
    if (message.trim() && !skipInbox) {
      if (!blobConfigured()) {
        finalReply = `${reply}\n\nCapture skipped: enable Vercel Blob (Storage → Blob).`
      } else {
        try {
          obsidianPath = await wiki.ingestRaw(wiki.titleFromMessage(message), message, 'chat')
          if (obsidianPath && !finalReply.includes(obsidianPath)) {
            finalReply = `${finalReply.trim()}\n\nSaved to \`${obsidianPath}\` — open Review to approve before it is filed.`
          }
        } catch {
          finalReply = `${reply}\n\nCapture failed writing to Vercel Blob.`
        }
      }
    }

    session.messages.push({
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      created_at: nowIso,
    })
    session.messages.push({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: finalReply,
      intent: 'general',
      created_at: new Date().toISOString(),
      ...(obsidianPath ? { obsidianPath } : {}),
    })
    session.updated_at = new Date().toISOString()
    if (session.messages.filter((m) => m.role === 'user').length === 1) {
      session.title = titleFromMessage(message)
    }

    if (blobConfigured()) {
      try {
        await saveState(state)
      } catch {
        /* chat still works without persisted sessions */
      }
    }

    sseWrite(res, 'message', finalReply)
    if (obsidianPath) sseWrite(res, 'obsidian', obsidianPath)
    sseWrite(res, 'intent', 'general')
    sseWrite(res, 'done', '1')
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Chat failed'
    sseWrite(res, 'error', msg)
  }
  res.end()
}

export default async function handler(req: VercelReq, res: ServerResponse): Promise<void> {
  const method = (req.method || 'GET').toUpperCase()
  const parts = routeParts(req)
  const path = parts.join('/')

  if (method === 'OPTIONS') {
    res.statusCode = 204
    res.end()
    return
  }

  if (path === 'health' && method === 'GET') {
    sendJson(res, 200, { status: 'ok', ...keyHealth(), ...claudeHealth(), blob: blobConfigured(), runtime: 'vercel' })
    return
  }

  if (!isAuthorized(req.headers as Record<string, string | string[] | undefined>)) {
    sendJson(res, 401, { detail: 'Unauthorized' })
    return
  }

  if (path === 'setup/openai' && method === 'GET') {
    sendJson(res, 200, await probeOpenAi())
    return
  }

  if (path === 'setup/claude' && method === 'GET') {
    sendJson(res, 200, await probeClaude())
    return
  }

  if (path === 'wiki/pending' && method === 'GET') {
    const items = await wiki.listPending()
    sendJson(res, 200, { items, count: items.length })
    return
  }

  if (path === 'wiki/item' && method === 'GET') {
    let notePath = ''
    try {
      notePath = new URL(req.url || '', 'http://n').searchParams.get('note') || ''
    } catch {
      notePath = ''
    }
    if (!notePath) {
      sendJson(res, 400, { detail: 'note query required' })
      return
    }
    try {
      sendJson(res, 200, await wiki.getItem(notePath))
    } catch (err) {
      sendJson(res, 404, { detail: err instanceof Error ? err.message : 'not found' })
    }
    return
  }

  if (path === 'wiki/ingest' && method === 'POST') {
    const body = parseBody(req)
    try {
      const inboxPath = await wiki.ingestRaw(
        String(body.title || 'Pasted note'),
        String(body.body || ''),
        String(body.source || 'upload'),
      )
      try {
        const proposed = await wiki.propose(inboxPath)
        sendJson(res, 200, proposed)
      } catch (err) {
        sendJson(res, 200, {
          path: inboxPath,
          status: 'inbox',
          detail: err instanceof Error ? err.message : 'Proposal failed — retry from Review.',
        })
      }
    } catch (err) {
      sendJson(res, 400, { detail: err instanceof Error ? err.message : 'ingest failed' })
    }
    return
  }

  if (path === 'wiki/propose' && method === 'POST') {
    const body = parseBody(req)
    try {
      sendJson(res, 200, await wiki.propose(String(body.path || '')))
    } catch (err) {
      sendJson(res, 400, { detail: err instanceof Error ? err.message : 'propose failed' })
    }
    return
  }

  if (path === 'wiki/approve' && method === 'POST') {
    const body = parseBody(req)
    try {
      sendJson(
        res,
        200,
        await wiki.approve(String(body.path || ''), typeof body.destination === 'string' ? body.destination : undefined),
      )
    } catch (err) {
      sendJson(res, 400, { detail: err instanceof Error ? err.message : 'approve failed' })
    }
    return
  }

  if (path === 'wiki/reject' && method === 'POST') {
    const body = parseBody(req)
    try {
      sendJson(res, 200, await wiki.reject(String(body.path || '')))
    } catch (err) {
      sendJson(res, 400, { detail: err instanceof Error ? err.message : 'reject failed' })
    }
    return
  }

  if (path === 'chat' && method === 'POST') {
    await handleChat(req, res)
    return
  }

  if (path === 'chat/sessions' && method === 'GET') {
    if (!blobConfigured()) {
      sendJson(res, 200, { sessions: [] })
      return
    }
    const state = await loadState()
    const limitRaw = req.query.limit
    const limit = Math.min(Number(Array.isArray(limitRaw) ? limitRaw[0] : limitRaw) || 30, 100)
    sendJson(res, 200, { sessions: state.sessions.slice(0, limit).map(sessionToApi) })
    return
  }

  if (path === 'chat/sessions' && method === 'POST') {
    const state = blobConfigured() ? await loadState() : { sessions: [] as StoredSession[], settings: {} }
    const nowIso = new Date().toISOString()
    const session: StoredSession = {
      id: crypto.randomUUID(),
      title: 'New chat',
      created_at: nowIso,
      updated_at: nowIso,
      messages: [],
    }
    state.sessions.unshift(session)
    if (blobConfigured()) await saveState(state)
    sendJson(res, 200, sessionToApi(session))
    return
  }

  if (parts[0] === 'chat' && parts[1] === 'sessions' && parts[3] === 'messages' && method === 'GET') {
    const id = parts[2]
    const state = blobConfigured() ? await loadState() : { sessions: [] as StoredSession[], settings: {} }
    const session = state.sessions.find((s) => s.id === id)
    if (!session) {
      sendJson(res, 404, { detail: 'session not found' })
      return
    }
    sendJson(res, 200, {
      session: sessionToApi(session),
      messages: session.messages,
    })
    return
  }

  if (path === 'auth/google/status' && method === 'GET') {
    sendJson(res, 200, { connected: false })
    return
  }

  if (path === 'plaid/items' && method === 'GET') {
    sendJson(res, 200, { items: [] })
    return
  }

  if (path === 'plaid/status' && method === 'GET') {
    sendJson(res, 200, { connected: false, items: [] })
    return
  }

  if (path === 'settings' && method === 'GET') {
    const state = blobConfigured() ? await loadState() : { sessions: [], settings: {} }
    sendJson(res, 200, state.settings)
    return
  }

  if (path === 'settings' && method === 'PATCH') {
    const state = blobConfigured() ? await loadState() : { sessions: [], settings: {} }
    const patch = parseBody(req)
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === null) continue
      state.settings[k] = Array.isArray(v) ? v.join(',') : String(v)
    }
    if (blobConfigured()) await saveState(state)
    sendJson(res, 200, state.settings)
    return
  }

  if (path === 'usage/today' && method === 'GET') {
    sendJson(res, 200, {
      date: formatInZone(zoneNow(), 'date'),
      estimated_cost_usd: 0,
      total_tokens: 0,
    })
    return
  }

  if (path === 'morning-brief/latest' && method === 'GET') {
    sendJson(res, 200, { date: '', path: null, content: null })
    return
  }

  sendJson(res, 501, {
    detail:
      'This endpoint is not on the Vercel runtime (chat + inbox capture only). Use the Mac app for Plaid, Gmail, uploads, and reading list.',
  })
}

export const config = {
  maxDuration: 10,
}
