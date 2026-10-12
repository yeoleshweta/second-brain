import { useCallback, useEffect, useMemo, useState } from 'react'
import { Check, FileText, Inbox, Loader2, RefreshCw, Sparkles, Trash2 } from 'lucide-react'
import {
  approveWikiItem,
  ingestWikiNote,
  listWikiPending,
  proposeWikiItem,
  rejectWikiItem,
  type WikiPendingItem,
} from '@/lib/api'

type Pane = 'raw' | 'proposed'

export function ReviewInbox() {
  const [items, setItems] = useState<WikiPendingItem[]>([])
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [source, setSource] = useState('meeting')
  const [showPaste, setShowPaste] = useState(false)
  const [pane, setPane] = useState<Pane>('raw')
  const [destination, setDestination] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await listWikiPending()
      setItems(rows)
      setSelectedPath((current) => {
        if (current && rows.some((r) => r.path === current)) return current
        return rows[0]?.path ?? null
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load review queue')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const selected = useMemo(
    () => items.find((item) => item.path === selectedPath) ?? null,
    [items, selectedPath],
  )

  useEffect(() => {
    if (!selected) {
      setDestination('')
      return
    }
    setDestination(selected.destination || '')
    setPane(selected.proposed ? 'proposed' : 'raw')
  }, [selected])

  async function run(path: string, fn: () => Promise<unknown>) {
    setBusy(path)
    setError(null)
    try {
      await fn()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed')
    } finally {
      setBusy(null)
    }
  }

  async function pasteIngest(e: React.FormEvent) {
    e.preventDefault()
    if (!body.trim()) return
    setBusy('ingest')
    setError(null)
    try {
      const result = await ingestWikiNote({
        title: title.trim() || 'Pasted note',
        body: body.trim(),
        source,
      })
      setTitle('')
      setBody('')
      setShowPaste(false)
      await refresh()
      if (result.path) setSelectedPath(result.path)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ingest failed')
    } finally {
      setBusy(null)
    }
  }

  const rawText = selected?.raw || selected?.raw_excerpt || ''
  const proposedText = selected?.proposed || selected?.proposed_excerpt || ''

  return (
    <div className="h-full min-h-0 flex flex-col md:flex-row overflow-hidden">
      <aside className="md:w-80 shrink-0 border-b md:border-b-0 md:border-r border-paper-200 bg-paper-50/80 overflow-y-auto">
        <div className="px-4 py-4 flex items-start justify-between gap-2">
          <div>
            <h1 className="text-base font-semibold text-paper-800">Review</h1>
            <p className="text-xs text-paper-500 mt-0.5">
              {items.length} waiting — nothing files until you approve
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            className="p-2 rounded-xl border border-paper-200 bg-paper-50 text-paper-600"
            aria-label="Refresh"
          >
            <RefreshCw size={15} />
          </button>
        </div>
        <div className="px-3 pb-3">
          <button
            type="button"
            onClick={() => setShowPaste((v) => !v)}
            className="w-full text-sm font-medium py-2 rounded-xl bg-accent-500 text-white"
          >
            {showPaste ? 'Close paste' : 'Paste meeting or clip'}
          </button>
        </div>
        {showPaste && (
          <form onSubmit={(e) => void pasteIngest(e)} className="px-3 pb-4 space-y-2">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Title"
              className="w-full text-sm border border-paper-200 rounded-xl px-3 py-2"
            />
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full text-sm border border-paper-200 rounded-xl px-3 py-2 bg-paper-50"
            >
              <option value="meeting">Meeting transcript</option>
              <option value="email">Email</option>
              <option value="clip">Web clip</option>
              <option value="upload">Other</option>
            </select>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Paste transcript or notes…"
              rows={7}
              className="w-full text-sm border border-paper-200 rounded-xl px-3 py-2"
            />
            <button
              type="submit"
              disabled={busy === 'ingest' || !body.trim()}
              className="w-full px-4 py-2 rounded-xl border border-paper-200 text-sm font-medium disabled:opacity-50"
            >
              {busy === 'ingest' ? 'Saving…' : 'Save for review'}
            </button>
          </form>
        )}
        {loading ? (
          <p className="text-sm text-paper-400 px-4 py-6">Loading Inbox…</p>
        ) : items.length === 0 ? (
          <div className="px-4 py-10 text-center text-paper-400">
            <Inbox size={24} className="mx-auto mb-2" />
            <p className="text-sm">Inbox is empty. Chat or paste a meeting.</p>
          </div>
        ) : (
          <ul className="px-2 pb-4 space-y-1">
            {items.map((item) => {
              const active = item.path === selectedPath
              return (
                <li key={item.path}>
                  <button
                    type="button"
                    onClick={() => setSelectedPath(item.path)}
                    className={`w-full text-left rounded-xl px-3 py-2.5 ${
                      active ? 'bg-paper-100' : 'hover:bg-paper-50'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-paper-800 truncate">{item.title}</span>
                      <span className={`text-[10px] uppercase tracking-wide shrink-0 ${
                        item.status === 'proposed' ? 'text-paper-600' : 'text-amber-700'
                      }`}>
                        {item.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-paper-400 mt-0.5 truncate">
                      {item.source || 'chat'} · {item.date_created}
                    </p>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </aside>

      <section className="flex-1 min-h-0 min-w-0 flex flex-col overflow-hidden">
        {error && (
          <p className="shrink-0 text-sm text-rust-400 bg-rust-100 border-b border-rust-200 px-4 py-2">{error}</p>
        )}
        {!selected ? (
          <div className="flex-1 flex items-center justify-center text-paper-400 text-sm px-6 text-center">
            Select a note to read the draft and approve or reject it.
          </div>
        ) : (
          <>
            <header className="shrink-0 px-4 md:px-6 py-4 border-b border-paper-200 bg-paper-50/90">
              <h2 className="text-lg font-semibold text-paper-800">{selected.title}</h2>
              <p className="text-[11px] font-mono text-paper-400 mt-1 break-all">{selected.path}</p>
              {selected.summary && (
                <p className="text-sm text-paper-600 mt-2">{selected.summary}</p>
              )}
              <label className="block mt-3">
                <span className="text-[10px] font-semibold uppercase tracking-wide text-paper-400">
                  File to (after approve)
                </span>
                <input
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  placeholder="Projects/example.md"
                  className="mt-1 w-full text-sm font-mono border border-paper-200 rounded-xl px-3 py-2"
                />
              </label>
              <div className="flex flex-wrap gap-2 mt-3">
                {selected.status === 'inbox' && (
                  <button
                    type="button"
                    disabled={busy === selected.path}
                    onClick={() => void run(selected.path, () => proposeWikiItem(selected.path))}
                    className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-xl bg-accent-500 text-white disabled:opacity-50"
                  >
                    {busy === selected.path ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                    Draft filing
                  </button>
                )}
                {selected.status === 'proposed' && (
                  <button
                    type="button"
                    disabled={busy === selected.path || !destination.trim()}
                    onClick={() => void run(selected.path, () => approveWikiItem(selected.path, destination.trim()))}
                    className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-xl bg-emerald-600 text-white disabled:opacity-50"
                  >
                    <Check size={14} /> Approve into vault
                  </button>
                )}
                <button
                  type="button"
                  disabled={busy === selected.path}
                  onClick={() => void run(selected.path, () => rejectWikiItem(selected.path))}
                  className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-xl border border-paper-200 text-paper-600"
                >
                  <Trash2 size={14} /> Reject
                </button>
              </div>
            </header>
            <div className="shrink-0 flex gap-1 px-4 md:px-6 pt-3">
              <button
                type="button"
                onClick={() => setPane('raw')}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg ${
                  pane === 'raw' ? 'bg-accent-500 text-white' : 'text-paper-500 bg-paper-100'
                }`}
              >
                Raw
              </button>
              <button
                type="button"
                onClick={() => setPane('proposed')}
                className={`inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg ${
                  pane === 'proposed' ? 'bg-accent-500 text-white' : 'text-paper-500 bg-paper-100'
                }`}
              >
                <FileText size={12} /> Proposed
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto px-4 md:px-6 py-3">
              <pre className="whitespace-pre-wrap text-sm text-paper-700 leading-relaxed font-sans">
                {pane === 'proposed'
                  ? (proposedText || 'No draft yet. Tap Draft filing after Claude has API credits.')
                  : (rawText || 'Empty note.')}
              </pre>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
