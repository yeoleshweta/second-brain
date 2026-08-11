import { useState, useEffect, useCallback, useRef } from 'react'
import { BookOpen, ExternalLink, Check, Trash2, RotateCcw, RefreshCw, Search, BookMarked, Smartphone } from 'lucide-react'
import { getReadingList, updateItem, deleteItem } from '@/lib/api'
import { openExternalUrl } from '@/lib/openExternal'
import { opensInAppReader } from '@/lib/readingItem'
import type { ReadingItem } from '@/lib/api'
import { ReadingReader } from '@/components/ReadingReader'

// ── Status config ─────────────────────────────────────────────────────────────
const STATUS_META: Record<string, { label: string; bg: string; fg: string }> = {
  unread:     { label: 'Unread',       bg: 'bg-accent-50',  fg: 'text-accent-500'  },
  in_progress:{ label: 'In Progress',  bg: 'bg-gold-100',   fg: 'text-gold-500'    },
  read:       { label: 'Read',         bg: 'bg-sage-100',   fg: 'text-sage-500'    },
}

type Filter = 'all' | 'unread' | 'in_progress' | 'read'

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all',         label: 'All'         },
  { id: 'unread',      label: 'Unread'      },
  { id: 'in_progress', label: 'In Progress' },
  { id: 'read',        label: 'Read'        },
]

/** True when the item came from Apple Books sync (url starts with apple-books://) */
function isAppleBook(item: ReadingItem): boolean {
  return (item.url ?? '').startsWith('apple-books://')
}

/** URL to open an Apple Books item.
 *
 *  We use https://books.apple.com/search?q= which iOS treats as a Universal
 *  Link and hands directly to the Books app. IMPORTANT: this only works when
 *  rendered as a real <a href> that the user taps — programmatic JS clicks
 *  do NOT trigger Universal Links on iOS. All Apple Books buttons must be
 *  <a> elements, never <button onClick>.
 */
function appleBooksOpenUrl(item: ReadingItem): string {
  const query = encodeURIComponent(`${item.title} ${item.source ?? ''}`.trim())
  return `https://books.apple.com/search?q=${query}`
}

function displayProgress(item: ReadingItem): number {
  const pct = item.progress ?? 0
  if (item.status === 'read') return Math.max(pct, 100)
  return pct
}

// ── Kind icon ─────────────────────────────────────────────────────────────────
function KindIcon({ kind }: { kind: string }) {
  const emoji =
    kind === 'paper' || kind === 'pdf' ? '📄'
    : kind === 'ebook' ? '📚'
    : kind === 'audiobook' ? '🎧'
    : kind === 'note' ? '📝'
    : '🔗'
  return (
    <div className="w-10 h-10 rounded-xl bg-paper-100 border border-paper-200 flex items-center justify-center text-base shrink-0">
      {emoji}
    </div>
  )
}

// ── Item card ─────────────────────────────────────────────────────────────────
function ItemCard({
  item,
  onRead,
  onMarkRead,
  onRemove,
}: {
  item: ReadingItem
  onRead: (item: ReadingItem) => void
  onMarkRead: (id: number) => void
  onRemove: (id: number) => void
}) {
  const id = item.id
  const status = item.status ?? 'unread'
  const meta = STATUS_META[status] ?? STATUS_META.unread
  const progress = displayProgress(item)
  const inApp = opensInAppReader(item)
  const appleBook = isAppleBook(item)

  return (
    <div className="bg-white rounded-2xl border border-paper-100 shadow-card hover:shadow-card-lg transition p-4 flex gap-3">
      <KindIcon kind={item.kind} />

      <div className="flex-1 min-w-0 space-y-1.5">
        {/* Title + external link */}
        <div className="flex items-start gap-2">
          {appleBook ? (
            <a
              href={appleBooksOpenUrl(item)}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-sm text-amber-700 leading-snug line-clamp-2 flex-1 text-left active:opacity-70 transition"
              aria-label={`Open "${item.title}" in Apple Books`}
            >
              {item.title}
            </a>
          ) : (
            <p className="font-semibold text-sm text-paper-800 leading-snug line-clamp-2 flex-1">
              {item.title}
            </p>
          )}
          {item.url && !appleBook && (
            <button
              type="button"
              onClick={() => openExternalUrl(item.url!)}
              className="shrink-0 touch-target flex items-center justify-center rounded-lg bg-paper-100 active:bg-accent-50 text-paper-400 active:text-accent-400 transition mt-0.5"
              aria-label="Open in Safari"
            >
              <ExternalLink size={13} />
            </button>
          )}
          {appleBook && (
            <a
              href={appleBooksOpenUrl(item)}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 touch-target flex items-center justify-center rounded-lg bg-amber-50 active:bg-amber-100 text-amber-500 active:text-amber-600 transition mt-0.5"
              aria-label="Open in Apple Books"
              title="Open in Apple Books"
            >
              <BookOpen size={13} />
            </a>
          )}
        </div>

        {/* Source + status pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          {item.source && (
            <span className="text-[10px] font-medium text-paper-400 bg-paper-100 px-2 py-0.5 rounded-full border border-paper-200">
              {item.source}
            </span>
          )}
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${meta.bg} ${meta.fg}`}>
            {meta.label}
          </span>
        </div>

        {/* Summary */}
        {item.summary && (
          <p className="text-xs text-paper-500 leading-relaxed line-clamp-2">{item.summary}</p>
        )}

        {/* Progress bar */}
        <div className="space-y-0.5 pt-0.5">
          <div className="h-1.5 bg-paper-200 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-accent-400 to-gold-400 transition-all duration-500"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
          <p className="text-[10px] text-paper-400">{progress}% complete</p>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 pt-0.5">
          {appleBook ? (
            /* Must be <a>, not <button>, so iOS Universal Links open the Books app */
            <a
              href={appleBooksOpenUrl(item)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs font-medium text-amber-600 active:text-amber-700 bg-amber-50 active:bg-amber-100 px-3 py-2 rounded-lg transition min-h-[44px] touch-manipulation"
            >
              <BookOpen size={14} />
              Open in Books
            </a>
          ) : (
            <button
              onClick={() => onRead(item)}
              className="flex items-center gap-1.5 text-xs font-medium text-accent-500 active:text-accent-600 bg-accent-50 active:bg-accent-100 px-3 py-2 rounded-lg transition min-h-[44px] touch-manipulation"
            >
              {inApp ? <BookMarked size={14} /> : <ExternalLink size={14} />}
              {inApp ? 'Read' : 'Open in Safari'}
            </button>
          )}
          {status !== 'read' && (
            <button
              onClick={() => onMarkRead(id)}
              className="flex items-center gap-1.5 text-xs font-medium text-sage-500 active:text-sage-600 bg-sage-100 active:bg-sage-200 px-3 py-2 rounded-lg transition min-h-[44px] touch-manipulation"
            >
              <Check size={14} />
              Mark read
            </button>
          )}
          {status === 'read' && (
            <button
              onClick={() => onMarkRead(id)}
              className="flex items-center gap-1.5 text-xs font-medium text-paper-400 active:text-paper-600 bg-paper-100 active:bg-paper-200 px-3 py-2 rounded-lg transition min-h-[44px] touch-manipulation"
            >
              <RotateCcw size={14} />
              Re-read
            </button>
          )}
          <button
            onClick={() => onRemove(id)}
            className="flex items-center gap-1.5 text-xs font-medium text-rust-400 active:text-rust-500 bg-rust-100 active:bg-rust-200 px-3 py-2 rounded-lg transition min-h-[44px] touch-manipulation"
          >
            <Trash2 size={14} />
            Remove
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Reading List view ─────────────────────────────────────────────────────────
export function ReadingList() {
  const [items, setItems] = useState<ReadingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const [readingItem, setReadingItem] = useState<ReadingItem | null>(null)
  const progressTimers = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getReadingList('unread,in_progress,read')
      setItems(data.items ?? [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const timers = progressTimers.current
    return () => {
      timers.forEach((t) => clearTimeout(t))
    }
  }, [])

  const handleProgressUpdate = useCallback((id: number, pct: number) => {
    let persisted = pct
    setItems((prev) =>
      prev.map((it) => {
        if (it.id !== id) return it
        const nextProgress = Math.max(it.progress ?? 0, pct)
        persisted = nextProgress
        const nextStatus =
          nextProgress >= 100
            ? ('read' as const)
            : nextProgress > 0
              ? ('in_progress' as const)
              : it.status
        return { ...it, progress: nextProgress, status: nextStatus }
      }),
    )
    const existing = progressTimers.current.get(id)
    if (existing) clearTimeout(existing)
    progressTimers.current.set(
      id,
      setTimeout(() => {
        updateItem(id, { progress: persisted }).catch(() => {})
        progressTimers.current.delete(id)
      }, 800),
    )
  }, [])

  async function handleMarkRead(id: number) {
    await updateItem(id, { status: 'read' }).catch(() => {})
    setItems((prev) =>
      prev.map((it) =>
        it.id === id ? { ...it, status: 'read' as const, progress: 100 } : it,
      ),
    )
  }

  async function handleRemove(id: number) {
    await deleteItem(id).catch(() => {})
    setItems((prev) => prev.filter((it) => it.id !== id))
  }

  function handleOpenItem(item: ReadingItem) {
    if (isAppleBook(item)) {
      openExternalUrl(appleBooksOpenUrl(item))
      return
    }
    if (item.url && !opensInAppReader(item)) {
      openExternalUrl(item.url)
      return
    }
    setReadingItem(item)
  }

  const filtered = items.filter((it) => {
    const matchFilter = filter === 'all' || (it.status ?? 'unread') === filter
    const q = query.toLowerCase()
    const matchSearch =
      !q ||
      it.title?.toLowerCase().includes(q) ||
      it.source?.toLowerCase().includes(q) ||
      it.summary?.toLowerCase().includes(q)
    return matchFilter && matchSearch
  })

  const unreadCount = items.filter((it) => (it.status ?? 'unread') === 'unread').length

  return (
    <div className="h-full flex flex-col bg-friends-cream">
      {readingItem && (
        <ReadingReader
          itemId={readingItem.id}
          title={readingItem.title}
          url={readingItem.url}
          initialProgress={readingItem.progress ?? 0}
          onProgress={(pct) => handleProgressUpdate(readingItem.id, pct)}
          onClose={() => setReadingItem(null)}
        />
      )}
      {/* Header — app bar shows "Reading" on mobile */}
      <div className="shrink-0 bg-friends-cream border-b border-paper-200 px-4 pt-3 pb-3">
        <div className="max-w-2xl mx-auto">
          <div className="hidden md:flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-accent-400 flex items-center justify-center">
                <BookOpen size={15} className="text-white" />
              </div>
              <div>
                <h1 className="font-serif text-base font-semibold text-paper-800 leading-none">
                  Reading List
                </h1>
                {unreadCount > 0 && (
                  <p className="text-[10px] text-paper-400 mt-0.5">
                    {unreadCount} unread
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={load}
              disabled={loading}
              className="touch-target flex items-center justify-center rounded-xl bg-white border border-paper-200 text-paper-400 active:text-accent-400 active:border-accent-200 transition shadow-card"
              aria-label="Refresh reading list"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>

          {/* Search + refresh row */}
          <div className="flex items-center gap-2 mb-3">
            <div className="flex-1 flex items-center gap-2 bg-white border border-paper-200 rounded-xl px-3 py-2.5 shadow-card min-h-[44px]">
              <Search size={16} className="text-paper-400 shrink-0" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search articles, papers…"
                enterKeyHint="search"
                autoComplete="off"
                className="input-ios flex-1 bg-transparent text-paper-800 placeholder:text-paper-400 outline-none"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="touch-target flex items-center justify-center text-paper-400 active:text-paper-600"
                  aria-label="Clear search"
                >
                  ✕
                </button>
              )}
            </div>
            <button
              onClick={load}
              disabled={loading}
              className="md:hidden touch-target shrink-0 flex items-center justify-center rounded-xl bg-white border border-paper-200 text-paper-400 active:text-accent-400 transition shadow-card"
              aria-label="Refresh reading list"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>

          {/* Filter pills */}
          <div className="flex gap-2 overflow-x-auto mobile-scroll scrollbar-hide pb-0.5">
            {FILTERS.map(({ id, label }) => {
              const count =
                id === 'all' ? items.length : items.filter((it) => (it.status ?? 'unread') === id).length
              return (
                <button
                  key={id}
                  onClick={() => setFilter(id)}
                  className={`shrink-0 text-xs font-semibold px-4 py-2.5 rounded-full transition min-h-[44px] touch-manipulation active:scale-95 ${
                    filter === id
                      ? 'bg-accent-400 text-white shadow-card'
                      : 'bg-white border border-paper-200 text-paper-500 active:border-accent-200'
                  }`}
                >
                  {label}
                  {count > 0 && (
                    <span
                      className={`ml-1.5 ${
                        filter === id ? 'text-white/70' : 'text-paper-400'
                      }`}
                    >
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Scrollable list */}
      <div className="flex-1 overflow-y-auto mobile-scroll px-4 py-4">
        <div className="max-w-2xl mx-auto space-y-3">
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="bg-white rounded-2xl border border-paper-100 p-4 animate-pulse">
                <div className="flex gap-3">
                  <div className="w-10 h-10 rounded-xl bg-paper-200" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 bg-paper-200 rounded w-3/4" />
                    <div className="h-2 bg-paper-200 rounded w-1/3" />
                    <div className="h-2 bg-paper-200 rounded w-full" />
                  </div>
                </div>
              </div>
            ))
          ) : filtered.length === 0 ? (
            <div className="text-center py-16">
              <div className="text-4xl mb-3">📭</div>
              <p className="font-serif text-base font-semibold text-paper-700">
                {query ? 'No matches found' : filter !== 'all' ? 'Nothing here yet' : 'Your reading list is empty'}
              </p>
              <p className="text-sm text-paper-400 mt-1">
                {!query && filter === 'all' && 'Tell Ross "save in notes https://…" to add articles'}
              </p>
            </div>
          ) : (
            filtered.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                onRead={handleOpenItem}
                onMarkRead={handleMarkRead}
                onRemove={handleRemove}
              />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
