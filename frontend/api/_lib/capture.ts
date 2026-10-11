export type LogType = 'food' | 'finance' | 'idea' | 'task' | 'exercise'

const TYPE_EMOJI: Record<LogType, string> = {
  food: '🍽',
  finance: '💸',
  idea: '💡',
  task: '✅',
  exercise: '🏃',
}

const TYPE_KEYWORDS: Record<LogType, string[]> = {
  food: ['ate', 'eaten', 'breakfast', 'lunch', 'dinner', 'snack', 'meal', 'calories', 'food', 'coffee'],
  finance: ['spent', 'paid', 'bought', 'groceries', 'receipt', 'budget', 'expense', 'dollar', '$'],
  idea: ['idea', 'insight', 'realized'],
  task: ['todo', 'to-do', 'task', 'remind me', 'need to', 'follow up', 'meeting'],
  exercise: ['workout', 'gym', 'exercise', 'yoga', 'walked', 'walk', 'jog', 'run '],
}

const INBOX_CAPTURE_RE = /\b(remember this|capture this|note this|dump this|write this down|put this in (?:my )?inbox|add to inbox|inbox this)\b/i

const CAPTURE_PREFIX_RE =
  /^(?:\[([^\]]+)\]\s*)?(?:remember this|capture this|note this|dump this|write this down|put this in (?:my )?inbox|add to inbox|inbox this)\s*[:\u2014\u2013\-]\s*/i

export const SYSTEM_PROMPT = `You are the user's Second Brain — one assistant, one vault, one daily note.

You answer helpfully and concisely (1–3 short paragraphs unless they ask for more).
This is a personal capture-first system:

- Markdown in the Obsidian vault is the source of truth. SQLite is chat history only.
- Structured writes go only under ## Log in today's daily note: 00-Inbox/Daily/YYYY-MM-DD.md.
- Five log types only: food, finance, idea, task, exercise.
- Unparseable captures go to 00-Inbox/Unsorted/. Failures go to 99-System/Logs/.
- You never file into 01–05, Career/Profile, or Context. Structure emerges from human review later.
- If they ask to remember / capture / write this down, acknowledge the Inbox save briefly.
- Do not invent character names, specialist personas, or sitcom branding.
- Do not claim you created atomic notes in 01-Knowledge or any domain folder.

If today's daily note is provided below, use it so replies stay relevant.
Do not rewrite existing log lines.`

export function isInboxThoughtDump(message: string): boolean {
  if (!INBOX_CAPTURE_RE.test(message || '')) return false
  const lowered = (message || '').toLowerCase()
  if (lowered.includes('http://') || lowered.includes('https://')) return false
  return !/\b(article|blog|pdf|document|reading list)\b/i.test(lowered)
}

function keywordHit(text: string, keyword: string): boolean {
  if (keyword === '$' || !/[A-Za-z0-9]/.test(keyword)) return text.includes(keyword)
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`(?<!\\w)${escaped}(?!\\w)`).test(text)
}

export function classifyLogType(text: string): LogType | null {
  const lowered = (text || '').toLowerCase()
  const hits: LogType[] = []
  for (const [typ, keywords] of Object.entries(TYPE_KEYWORDS) as [LogType, string[]][]) {
    if (keywords.some((kw) => keywordHit(lowered, kw))) hits.push(typ)
  }
  return hits.length === 1 ? hits[0] : null
}

function stripCapturePrefix(message: string): string {
  const stripped = (message || '').replace(CAPTURE_PREFIX_RE, '').trim()
  return stripped || (message || '').trim()
}

function formatLogEntry(text: string, typ: LogType, src: string, time: string): string {
  return `- ${time} ${TYPE_EMOJI[typ]} **${typ}** :: ${text} [src:: ${src}]`
}

function builtinDailyNote(today: string, created: string): string {
  return (
    `---\n` +
    `type: daily\n` +
    `date: ${today}\n` +
    `created: ${created}\n` +
    `mood:\n` +
    `energy:\n` +
    `---\n\n` +
    `# ${today}\n\n` +
    `## Log\n` +
    `<!-- bot appends here, newest at bottom -->\n\n` +
    `## Notes\n` +
    `<!-- your own free writing -->\n\n` +
    `## Review\n` +
    `- [ ] Triage captures\n`
  )
}

function insertUnderHeading(content: string, heading: string, entryLine: string): string {
  const entry = entryLine.replace(/\n$/, '') + '\n'
  const body = content.endsWith('\n') || !content ? content : content + '\n'
  const lines = body.split(/(?<=\n)/)
  const target = heading.trim()
  const headingIdx = lines.findIndex((line) => line.trim() === target)
  if (headingIdx < 0) return body + `\n${target}\n${entry}`
  let nextIdx = -1
  for (let i = headingIdx + 1; i < lines.length; i++) {
    if (lines[i].startsWith('## ') && lines[i].trim() !== target) {
      nextIdx = i
      break
    }
  }
  if (nextIdx < 0) return lines.join('') + entry
  return lines.slice(0, nextIdx).join('') + entry + lines.slice(nextIdx).join('')
}

function linesPreserved(before: string, after: string): boolean {
  const old = before.split('\n').map((ln) => ln.replace(/\n$/, ''))
  const neu = after.split('\n').map((ln) => ln.replace(/\n$/, ''))
  let cursor = 0
  for (const line of old) {
    const idx = neu.indexOf(line, cursor)
    if (idx < 0) return false
    cursor = idx + 1
  }
  return true
}

export function zoneNow(): Date {
  return new Date()
}

export function formatInZone(d: Date, pattern: 'date' | 'time' | 'created'): string {
  const tz = process.env.TZ || 'America/New_York'
  if (pattern === 'date') {
    return d.toLocaleDateString('en-CA', { timeZone: tz })
  }
  if (pattern === 'time') {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(d)
    return parts
  }
  const date = d.toLocaleDateString('en-CA', { timeZone: tz })
  const time = new Intl.DateTimeFormat('en-GB', {
    timeZone: tz,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d)
  return `${date}T${time}`
}

export function dailyPath(today: string): string {
  return `00-Inbox/Daily/${today}.md`
}

export function blobVaultPath(rel: string): string {
  return `vault/${rel.replace(/^\/+/, '')}`
}

export function buildSystemMessage(daily: string, todayPath: string): string {
  if (!daily.trim()) return SYSTEM_PROMPT
  const clipped = daily.slice(0, 4000)
  return `${SYSTEM_PROMPT}\n\nToday's daily note (\`${todayPath}\`):\n${clipped}`
}

export function prepareCapture(message: string): {
  dailyPathRel: string
  unsortedPathRel: string | null
  unsortedBody: string | null
  dailyEntry: string | null
  today: string
  created: string
} {
  const now = zoneNow()
  const today = formatInZone(now, 'date')
  const created = formatInZone(now, 'created')
  const stampTime = formatInZone(now, 'time')
  const stamp = `${today}-${stampTime.replace(':', '')}00`
  const raw = (message || '').trim() || '(empty capture)'
  const cleaned = stripCapturePrefix(raw)
  const typ = classifyLogType(cleaned)
  if (typ === null) {
    return {
      dailyPathRel: dailyPath(today),
      unsortedPathRel: `00-Inbox/Unsorted/${stamp}.md`,
      unsortedBody:
        `---\n` +
        `type: unsorted\n` +
        `created: ${created}\n` +
        `src: user\n` +
        `---\n\n` +
        `${raw}\n`,
      dailyEntry: null,
      today,
      created,
    }
  }
  return {
    dailyPathRel: dailyPath(today),
    unsortedPathRel: null,
    unsortedBody: null,
    dailyEntry: formatLogEntry(cleaned, typ, 'user', stampTime),
    today,
    created,
  }
}

export function applyDailyCapture(existing: string | null, entry: string, today: string, created: string): string {
  const base = existing && existing.trim() ? existing : builtinDailyNote(today, created)
  const updated = insertUnderHeading(base, '## Log', entry)
  if (!linesPreserved(base, updated)) {
    throw new Error('refusing daily write: existing lines would change')
  }
  return updated
}

export function systemLogLine(detail: string): { path: string; line: string; seed: string } {
  const now = zoneNow()
  const today = formatInZone(now, 'date')
  const ts = formatInZone(now, 'time')
  const path = `99-System/Logs/${today}.md`
  const line = `- ${ts} ${detail}\n`
  return { path, line, seed: `# ${today}\n\n${line}` }
}

export function appendLog(existing: string | null, line: string, seed: string): string {
  if (!existing) return seed
  return existing.endsWith('\n') ? existing + line : `${existing}\n${line}`
}
