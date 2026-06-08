import { useState } from 'react'
import { BookMarked, Check, Loader2 } from 'lucide-react'
import { downloadGutenbergBook } from '@/lib/api'
import { ExternalOpenButton } from '@/components/ExternalOpenButton'
import type { BookItem } from '@/types'

interface Props {
  items: BookItem[]
}

function oceanLabel(item: BookItem): string {
  if (item.source === 'oceanofpdf') {
    return item.is_search ? 'Open search in Safari' : 'Open book in Safari'
  }
  if (item.source === 'web') {
    return 'Open PDF link in Safari'
  }
  return 'Open in Safari'
}

export function BookPicker({ items }: Props) {
  const [downloaded, setDownloaded] = useState<Set<string>>(new Set())
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(items[0]?.id ?? null)
  const [error, setError] = useState<string | null>(null)

  async function handleDownload(item: BookItem) {
    if (!item.gutenberg_id || !item.downloadable) return
    setLoadingId(item.id)
    setError(null)
    try {
      await downloadGutenbergBook(item.gutenberg_id)
      setDownloaded((prev) => new Set(prev).add(item.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <div className="mt-2 space-y-2">
      {items.map((item) => {
        const isDone = downloaded.has(item.id)
        const isExpanded = expanded === item.id
        const isLoading = loadingId === item.id
        const isOcean = item.source === 'oceanofpdf'

        return (
          <div
            key={item.id}
            className="bg-white border border-paper-100 rounded-xl shadow-card overflow-hidden"
          >
            <div className="px-3 py-2.5">
              <button
                type="button"
                className="w-full text-left min-h-[44px] py-1 touch-manipulation"
                onClick={() => setExpanded(isExpanded ? null : item.id)}
              >
                <div className="flex items-start gap-2">
                  <div className="w-7 h-7 rounded-lg bg-paper-100 flex items-center justify-center text-sm shrink-0">
                    {item.kind === 'audiobook' ? '🎧' : isOcean ? '📖' : item.source === 'web' ? '🔗' : '📚'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-paper-800 leading-snug line-clamp-2">
                      {item.title}
                    </p>
                    <p className="text-[10px] text-paper-400 mt-0.5">
                      {item.authors} · {item.source}
                    </p>
                  </div>
                </div>
                <p
                  className={`text-[11px] text-paper-600 leading-relaxed mt-2 ml-9 ${
                    isExpanded ? '' : 'line-clamp-2'
                  }`}
                >
                  {item.summary}
                </p>
              </button>

              <div className="flex flex-col sm:flex-row flex-wrap gap-2 mt-2 ml-9">
                {item.downloadable && item.gutenberg_id && (
                  <button
                    type="button"
                    onClick={() => handleDownload(item)}
                    disabled={isDone || isLoading}
                    className={`flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg min-h-[44px] transition touch-manipulation ${
                      isDone
                        ? 'bg-sage-100 text-sage-600'
                        : 'bg-accent-50 text-accent-500 hover:bg-accent-100'
                    }`}
                  >
                    {isLoading ? (
                      <Loader2 size={11} className="animate-spin" />
                    ) : isDone ? (
                      <Check size={11} />
                    ) : (
                      <BookMarked size={11} />
                    )}
                    {isDone ? 'Added to list' : 'Download'}
                  </button>
                )}
                {item.url && (
                  <ExternalOpenButton
                    url={item.url}
                    label={oceanLabel(item)}
                    variant={isOcean ? 'primary' : 'secondary'}
                    hint={
                      isOcean
                        ? 'Leaves Central Perk and opens Safari so you can download there.'
                        : undefined
                    }
                  />
                )}
              </div>
            </div>
          </div>
        )
      })}
      {error && <p className="text-[11px] text-rust-500 px-1">{error}</p>}
    </div>
  )
}
