const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
const ANTHROPIC_VERSION = '2023-06-01'

export function anthropicKey(): string {
  return (process.env.ANTHROPIC_API_KEY || '').trim()
}

export function claudeHealth() {
  const key = anthropicKey()
  return {
    anthropic_key_present: Boolean(key),
    anthropic_key_format_ok: key.startsWith('sk-ant-') && key.length >= 20,
  }
}

export async function probeClaude(): Promise<{ ok: boolean; code: string }> {
  const key = anthropicKey()
  if (!key) return { ok: false, code: 'missing' }
  if (!claudeHealth().anthropic_key_format_ok) return { ok: false, code: 'malformed' }
  try {
    const text = await completeClaude({
      system: 'Reply with the single word ok.',
      user: 'ping',
      maxTokens: 8,
    })
    return { ok: Boolean(text.trim()), code: text.trim() ? 'ok' : 'empty' }
  } catch (err) {
    const msg = err instanceof Error ? err.message : ''
    if (msg.includes('401')) return { ok: false, code: 'invalid_api_key' }
    if (msg.includes('429') || /credit/i.test(msg)) return { ok: false, code: 'billing' }
    return { ok: false, code: 'unreachable' }
  }
}

export async function completeClaude(opts: {
  system: string
  user: string
  messages?: { role: string; content: string }[]
  maxTokens?: number
}): Promise<string> {
  const key = anthropicKey()
  if (!key) throw new Error('ANTHROPIC_API_KEY is not set on Vercel')
  const turns: { role: string; content: string }[] = []
  for (const turn of opts.messages || []) {
    if ((turn.role === 'user' || turn.role === 'assistant') && turn.content) {
      turns.push({ role: turn.role, content: turn.content })
    }
  }
  turns.push({ role: 'user', content: opts.user })
  const resp = await fetch(ANTHROPIC_URL, {
    method: 'POST',
    headers: {
      'x-api-key': key,
      'anthropic-version': ANTHROPIC_VERSION,
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-5',
      max_tokens: opts.maxTokens ?? 1024,
      system: opts.system,
      messages: turns,
    }),
  })
  if (!resp.ok) {
    const body = await resp.text()
    if (resp.status === 400 && /credit/i.test(body)) {
      throw new Error('Claude billing: add credits at console.anthropic.com')
    }
    throw new Error(`Claude HTTP ${resp.status}`)
  }
  const data = (await resp.json()) as { content?: { type?: string; text?: string }[] }
  return (data.content || [])
    .filter((p) => p.type === 'text')
    .map((p) => p.text || '')
    .join('')
    .trim()
}

export function publicClaudeError(err: unknown): string {
  const msg = err instanceof Error ? err.message : ''
  if (/billing|credit/i.test(msg)) {
    return 'Claude has no API credits. Add billing at https://console.anthropic.com/settings/billing then retry Review.'
  }
  if (msg.includes('401')) {
    return 'Anthropic rejected ANTHROPIC_API_KEY. Set it in Vercel env and redeploy.'
  }
  if (msg.includes('ANTHROPIC_API_KEY')) {
    return 'ANTHROPIC_API_KEY is not set on Vercel. Add it in Project Settings → Environment Variables.'
  }
  return 'Claude request failed.'
}
