import { useCallback, useEffect, useState } from 'react'
import { BookOpen, ExternalLink, Trash2, CheckCircle, Edit3, X } from 'lucide-react'
import { getReadingList, updateItem, deleteItem } from '@/lib/api'
import type { ReadingItem, ReadingStats } from '@/lib/api'

const STATUS_LABELS: Record<string, string> = {
  unread: 'Unread',
  in_progress: 'In progress',
  read: 'Read',
}

const STATUS_COLORS: Record<string, string> = {
  unread: 'bg-ink-600 text-ink-200',
  in_progress: 'bg-amber-900 text-amber-200',
  read: 'bg-emerald-900 text-emerald-200',
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="w-full bg-ink-700 rounded-full h-1.5 mt-1">
      <div
        className="bg-blue-500 h-1.5 rounded-full transition-all"
        style={{ width: `${value}%` }}
      />
    </div>
  )
}

function EditProgressModal({
  item,
  onSave,
  onClose,
}: {
  item: ReadingItem
  onSave: (pct: number) => void
  onClose: () => void
}) {
  const [val, setVal] = useState(String(item.progress))
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-ink-800 border border-ink-700 rounded-xl p-6 w-full max-w-sm">
        <div className="flex justify-between items-start mb-4">
          <h3 className="font-semibold text-ink-100 pr-4 leading-snug">{item.title}</h3>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-200 shrink-0">
            <X size={18} />
          </button>
        </div>
        <label className="block text-sm text-ink-300 mb-2">Progress (%)</label>
        <input
          type="number"
          min={0}
          max={100}
          value={val}
          onChange={(e) => setVal(e.target.value)}
          className="w-full bg-ink-700 border border-ink-600 rounded-md px-3 py-2 text-ink-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex gap-2 mt-4">
          <button
            onClick={() => onSave(Math.max(0, Math.min(100, Number(val) || 0)))}
            className="flex-1 bg-blue-600 hover:bg-blue-500 text-white rounded-md py-2 text-sm font-medium min-h-[44px]"
          >
            Save
          </button>
          <button
            onClick={onClose}
            className="flex-1 bg-ink-700 hover:bg-ink-600 text-ink-200 rounded-md py-2 text-sm min-h-[44px]"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

export function ReadingList() {
  const [items, setItems] = useState<ReadingItem[]>([])
  const [stats, setStats] = useState<ReadingStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingItem, setEditingItem] = useState<ReadingItem | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await getReadingList()
      setItems(data.items)
      setStats(data.stats)
    } catch (err) {
      console.error('Failed to load reading list', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 30_000)
    return () => clearInterval(interval)
  }, [load])

  const handleMarkRead = async (item: ReadingItem) => {
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: 'read' } : i)))
    try {
      await updateItem(item.id, { status: 'read' })
      await load()
    } catch (err) {
      console.error('Mark read failed', err)
      await load()
    }
  }

  const handleDelete = async (item: ReadingItem) => {
    if (!window.confirm(`Delete "${item.title}"?`)) return
    setItems((prev) => prev.filter((i) => i.id !== item.id))
    try {
      await deleteItem(item.id)
      await load()
    } catch (err) {
      console.error('Delete failed', err)
      await load()
    }
  }

  const handleSaveProgress = async (item: ReadingItem, pct: number) => {
    setEditingItem(null)
    setItems((prev) =>
      prev.map((i) =>
        i.id === item.id
          ? { ...i, progress: pct, status: pct >= 100 ? 'read' : pct > 0 ? 'in_progress' : 'unread' }
          : i,
      ),
    )
    try {
      await updateItem(item.id, { progress: pct })
      await load()
    } catch (err) {
      console.error('Progress update failed', err)
      await load()
    }
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-ink-400 text-sm">Loading reading list…</div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 md:px-6 py-4 border-b border-ink-700">
        <div className="flex items-center gap-2 mb-2">
          <BookOpen size={20} className="text-blue-400" />
          <h2 className="font-semibold text-ink-100">Reading List</h2>
        </div>
        {stats && (
          <>
            <p className="text-sm text-ink-400">
              📚 {stats.total} saved · {stats.read} read ({stats.percent_done}%)
            </p>
            <div className="mt-2 w-full bg-ink-700 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all"
                style={{ width: `${stats.percent_done}%` }}
              />
            </div>
          </>
        )}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4">
        {items.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-4xl mb-3">📚</div>
            <p className="text-ink-400 text-sm">Your reading list is empty.</p>
            <p className="text-ink-500 text-xs mt-1">
              Save something with "save in notes &lt;url&gt;" in chat.
            </p>
          </div>
        ) : (
          <ul className="space-y-3">
            {items.map((item) => (
              <li
                key={item.id}
                className="bg-ink-800 border border-ink-700 rounded-xl p-4 flex flex-col md:flex-row md:items-start gap-3"
              >
                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-start gap-2 mb-1">
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-ink-100 hover:text-blue-400 flex items-center gap-1 break-words"
                      >
                        {item.title}
                        <ExternalLink size={12} className="shrink-0 opacity-60" />
                      </a>
                    ) : (
                      <span className="font-medium text-ink-100">{item.title}</span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs mt-1">
                    {item.source && (
                      <span className="bg-ink-700 text-ink-300 px-2 py-0.5 rounded-full">
                        {item.source}
                      </span>
                    )}
                    <span
                      className={`px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[item.status] || STATUS_COLORS.unread}`}
                    >
                      {STATUS_LABELS[item.status] || item.status}
                    </span>
                    {item.progress > 0 && (
                      <span className="text-ink-400">{item.progress}%</span>
                    )}
                  </div>
                  {item.progress > 0 && <ProgressBar value={item.progress} />}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  {item.status !== 'read' && (
                    <>
                      <button
                        onClick={() => handleMarkRead(item)}
                        title="Mark as read"
                        className="min-h-[44px] min-w-[44px] flex items-center justify-center text-emerald-400 hover:text-emerald-300 hover:bg-ink-700 rounded-lg transition"
                      >
                        <CheckCircle size={18} />
                      </button>
                      <button
                        onClick={() => setEditingItem(item)}
                        title="Edit progress"
                        className="min-h-[44px] min-w-[44px] flex items-center justify-center text-blue-400 hover:text-blue-300 hover:bg-ink-700 rounded-lg transition"
                      >
                        <Edit3 size={18} />
                      </button>
                    </>
                  )}
                  <button
                    onClick={() => handleDelete(item)}
                    title="Delete"
                    className="min-h-[44px] min-w-[44px] flex items-center justify-center text-rose-400 hover:text-rose-300 hover:bg-ink-700 rounded-lg transition"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Edit progress modal */}
      {editingItem && (
        <EditProgressModal
          item={editingItem}
          onSave={(pct) => handleSaveProgress(editingItem, pct)}
          onClose={() => setEditingItem(null)}
        />
      )}
    </div>
  )
}
