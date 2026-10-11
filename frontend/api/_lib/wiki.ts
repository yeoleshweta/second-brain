import { blobConfigured, listPaths, readText, writeText } from './blob'
import { completeClaude } from './claude'

const INBOX_PREFIX = 'vault/Inbox/'
const WIKI_DEST = ['Notes/', 'People/', 'Projects/', 'Concepts/', 'Briefings/'] as const

const PROCESSING_PROMPT = `You are a knowledge management assistant.
Process the following raw note and return a JSON object with these fields:
- "summary": A 2-3 sentence summary
- "key_concepts": Array of 3-7 core concepts
- "people": Array of people referenced
- "action_items": Array of tasks
- "related_topics": Array of topics
- "destination_folder": One of Notes, People, Projects, Concepts
- "destination_title": Short filename title without .md
- "processed_content": Clean Markdown with [[wiki-links]]

This is a PROPOSAL only. A human must approve before it is filed.

Raw note:
{content}

Return only valid JSON.`

export type WikiItem = {
  path: string
  title: string
  status: string
  source: string
  destination: string
  summary: string
  raw: string
  proposed: string
  raw_excerpt: string
  proposed_excerpt: string
  date_created: string
}

function slugify(title: string): string {
  const slug = (title || 'note').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return (slug || 'note').slice(0, 72)
}

function assertDest(path: string): void {
  const n = path.replace(/\\/g, '/').replace(/^\/+/, '')
  if (!WIKI_DEST.some((p) => n === p.slice(0, -1) || n.startsWith(p))) {
    throw new Error(`Refusing wiki destination: ${path}`)
  }
}

function parseFront(md: string): { meta: Record<string, string>; body: string } {
  if (!md.startsWith('---')) return { meta: {}, body: md }
  const end = md.indexOf('\n---', 3)
  if (end < 0) return { meta: {}, body: md }
  const yaml = md.slice(4, end)
  const body = md.slice(end + 4).replace(/^\n/, '')
  const meta: Record<string, string> = {}
  for (const line of yaml.split('\n')) {
    const i = line.indexOf(':')
    if (i < 0) continue
    meta[line.slice(0, i).trim()] = line.slice(i + 1).trim().replace(/^"|"$/g, '')
  }
  return { meta, body }
}

function splitRawProposed(body: string): { raw: string; proposed: string } {
  if (body.includes('## Proposed')) {
    const [rawPart, ...rest] = body.split('## Proposed')
    return {
      raw: rawPart.replace('## Raw', '').trim(),
      proposed: rest.join('## Proposed').trim(),
    }
  }
  return { raw: body.replace('## Raw', '').trim(), proposed: '' }
}

function dumpInbox(opts: {
  title: string
  status: string
  source: string
  destination?: string
  summary?: string
  raw: string
  proposed?: string
  dateCreated?: string
}): string {
  const today = new Date().toISOString().slice(0, 10)
  const dest = opts.destination || ''
  const summary = opts.summary || ''
  let body = `## Raw\n\n${opts.raw.trim()}\n`
  if (opts.proposed?.trim()) body += `\n## Proposed\n\n${opts.proposed.trim()}\n`
  return (
    `---\n` +
    `title: ${JSON.stringify(opts.title)}\n` +
    `date_created: ${opts.dateCreated || today}\n` +
    `date_modified: ${today}\n` +
    `status: ${opts.status}\n` +
    `source: ${opts.source}\n` +
    `destination: ${dest}\n` +
    `summary: ${JSON.stringify(summary)}\n` +
    `---\n\n` +
    body
  )
}

function toItem(relPath: string, md: string): WikiItem {
  const { meta, body } = parseFront(md)
  const { raw, proposed } = splitRawProposed(body)
  return {
    path: relPath,
    title: meta.title || relPath,
    status: meta.status || 'inbox',
    source: meta.source || '',
    destination: meta.destination || '',
    summary: meta.summary || '',
    raw,
    proposed,
    raw_excerpt: raw.slice(0, 400),
    proposed_excerpt: proposed.slice(0, 400),
    date_created: meta.date_created || '',
  }
}

function blobToRel(pathname: string): string {
  return pathname.startsWith('vault/') ? pathname.slice(6) : pathname
}

export async function ingestRaw(title: string, body: string, source: string): Promise<string> {
  if (!blobConfigured()) throw new Error('Enable Vercel Blob on this project')
  const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)
  const rel = `Inbox/${stamp}-${slugify(title)}.md`
  await writeText(`vault/${rel}`, dumpInbox({ title, status: 'inbox', source, raw: body }), 'text/markdown')
  return rel
}

export async function listPending(): Promise<WikiItem[]> {
  if (!blobConfigured()) return []
  const paths = await listPaths(INBOX_PREFIX)
  const out: WikiItem[] = []
  for (const p of paths) {
    if (!p.endsWith('.md')) continue
    const md = await readText(p)
    if (!md) continue
    const item = toItem(blobToRel(p), md)
    if (item.status === 'inbox' || item.status === 'proposed') out.push(item)
  }
  return out.sort((a, b) => a.path.localeCompare(b.path))
}

export async function getItem(rel: string): Promise<WikiItem> {
  const n = rel.replace(/\\/g, '/').replace(/^\/+/, '')
  if (!n.startsWith('Inbox/') || n.includes('..')) throw new Error('can only read Inbox notes')
  const md = await readText(`vault/${n}`)
  if (!md) throw new Error('not found')
  return toItem(n, md)
}

export async function propose(rel: string): Promise<WikiItem> {
  const item = await getItem(rel)
  const text = await completeClaude({
    system: 'Return only JSON. This is a filing proposal; a human will approve it.',
    user: PROCESSING_PROMPT.replace('{content}', item.raw.slice(0, 12000)),
    maxTokens: 4096,
  })
  let data: Record<string, unknown>
  try {
    const cleaned = text.replace(/^```json\s*/i, '').replace(/^```/, '').replace(/```$/, '').trim()
    data = JSON.parse(cleaned) as Record<string, unknown>
  } catch {
    throw new Error('Claude did not return JSON')
  }
  let folder = String(data.destination_folder || 'Notes').replace(/\//g, '')
  if (!['Notes', 'People', 'Projects', 'Concepts'].includes(folder)) folder = 'Notes'
  const destTitle = String(data.destination_title || item.title)
  const destination = `${folder}/${slugify(destTitle)}.md`
  assertDest(destination)
  const processed = String(data.processed_content || '').trim()
  const md = dumpInbox({
    title: item.title,
    status: 'proposed',
    source: item.source,
    destination,
    summary: String(data.summary || ''),
    raw: item.raw,
    proposed: processed,
    dateCreated: item.date_created,
  })
  await writeText(`vault/${rel}`, md, 'text/markdown')
  return toItem(rel, md)
}

export async function approve(rel: string, destination?: string): Promise<{ path: string; destination: string; status: string }> {
  const item = await getItem(rel)
  if (!item.proposed.trim()) throw new Error('no proposal to approve — run propose first')
  const dest = (destination || item.destination).replace(/\\/g, '/').replace(/^\/+/, '')
  assertDest(dest)
  const filed =
    `---\n` +
    `title: ${JSON.stringify(item.title)}\n` +
    `status: processed\n` +
    `source: ${item.source}\n` +
    `inbox: ${rel}\n` +
    `---\n\n` +
    `${item.proposed.trim()}\n`
  await writeText(`vault/${dest}`, filed, 'text/markdown')
  const md = dumpInbox({
    title: item.title,
    status: 'processed',
    source: item.source,
    destination: dest,
    summary: item.summary,
    raw: item.raw,
    proposed: item.proposed,
    dateCreated: item.date_created,
  })
  await writeText(`vault/${rel}`, md, 'text/markdown')
  return { path: rel, destination: dest, status: 'processed' }
}

export async function reject(rel: string): Promise<{ path: string; status: string }> {
  const item = await getItem(rel)
  const md = dumpInbox({
    title: item.title,
    status: 'rejected',
    source: item.source,
    destination: item.destination,
    summary: item.summary,
    raw: item.raw,
    proposed: item.proposed,
    dateCreated: item.date_created,
  })
  await writeText(`vault/${rel}`, md, 'text/markdown')
  return { path: rel, status: 'rejected' }
}

export function titleFromMessage(message: string): string {
  const t = (message || '').trim().split('\n')[0].replace(/\s+/g, ' ')
  return (t ? t.slice(0, 72) : 'Chat capture').trim()
}
