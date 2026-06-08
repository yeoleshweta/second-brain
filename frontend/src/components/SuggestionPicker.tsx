import { useState } from 'react'
import { BookMarked, Check, ExternalLink, Eye, Loader2 } from 'lucide-react'
import { addSuggestionsToReadingList } from '@/lib/api'
import { openExternalUrl } from '@/lib/openExternal'
import type { SuggestItem } from '@/types'

interface Props {
  items: SuggestItem[]
}

export function SuggestionPicker({ items }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [added, setAdded] = useState<Set<string>>(new Set())
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const addable = items.filter((i) => !i.in_list && !added.has(i.id))
  const selectedAddable = addable.filter((i) => selected.has(i.id))

  function toggle(id: string, inList: boolean) {
    if (inList || added.has(id)) return
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleAddSelected() {
    if (selectedAddable.length === 0) return
    setLoading(true)
    setError(null)
    try {
      await addSuggestionsToReadingList(
        selectedAddable.map((i) => ({
          url: i.url,
          title: i.title,
          summary: i.summary,
          source: i.source,
          kind: i.kind,
          tags: i.tag || '',
          pdf_url: i.pdf_preview_url,
        })),
      )
      setAdded((prev) => {
        const next = new Set(prev)
        selectedAddable.forEach((i) => next.add(i.id))
        return next
      })
      setSelected(new Set())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add items')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mt-2 space-y-2 w-full min-w-0">
      {items.map((item) => {
        const isAdded = item.in_list || added.has(item.id)
        const isSelected = selected.has(item.id)
        const isExpanded = expanded === item.id
        const hasPreview = Boolean(item.pdf_preview_url)

        return (
          <div
            key={item.id}
            className={`bg-white border rounded-xl shadow-card overflow-hidden transition w-full min-w-0 ${
              isSelected ? 'border-accent-300 ring-1 ring-accent-200' : 'border-paper-100'
            }`}
          >
            <div className="flex items-start gap-2.5 px-3 py-3 min-h-[48px]">
              <button
                type="button"
                onClick={() => toggle(item.id, item.in_list)}
                disabled={isAdded || loading}
                className={`touch-target flex items-center justify-center rounded-md border shrink-0 transition ${
                  isAdded
                    ? 'bg-sage-100 border-sage-300 text-sage-500'
                    : isSelected
                      ? 'bg-accent-400 border-accent-400 text-white'
                      : 'border-paper-300 hover:border-accent-300'
                } ${isAdded ? 'cursor-default' : ''}`}
                aria-label={isAdded ? 'Already on list' : isSelected ? 'Deselect' : 'Select'}
              >
                {(isAdded || isSelected) && <Check size={12} />}
              </button>

              <div className="flex-1 min-w-0">
                <button
                  type="button"
                  className="w-full text-left touch-manipulation py-1"
                  onClick={() => setExpanded(isExpanded ? null : item.id)}
                >
                  <div className="flex items-start gap-2">
                    <div className="w-7 h-7 rounded-lg bg-paper-100 flex items-center justify-center text-sm shrink-0">
                      {item.kind === 'paper' ? '📄' : item.kind === 'ebook' ? '📚' : '🔗'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-paper-800 leading-snug line-clamp-2">
                        {item.title}
                      </p>
                      <p className="text-[10px] text-paper-400 mt-0.5">
                        {item.source}
                        {item.est_minutes ? ` · ~${item.est_minutes} min` : ''}
                        {item.tag ? ` · ${item.tag}` : ''}
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
                  {!isExpanded && item.summary.length > 120 && (
                    <span className="text-[10px] text-accent-500 mt-1 ml-9 inline-block">
                      Show more
                    </span>
                  )}
                </button>
              </div>

              <div className="flex flex-col gap-1 shrink-0">
                {hasPreview && (
                  <button
                    type="button"
                    onClick={() => setExpanded(isExpanded ? null : item.id)}
                    className={`touch-target flex items-center justify-center rounded-lg transition ${
                      isExpanded
                        ? 'bg-accent-100 text-accent-500'
                        : 'bg-paper-100 text-paper-400 active:bg-accent-50 active:text-accent-400'
                    }`}
                    aria-label={isExpanded ? 'Hide PDF preview' : 'Preview PDF'}
                  >
                    <Eye size={13} />
                  </button>
                )}
                {item.url && (
                  <button
                    type="button"
                    onClick={() => openExternalUrl(item.url!)}
                    className="touch-target flex items-center justify-center rounded-lg bg-paper-100 active:bg-accent-50 text-paper-400 active:text-accent-400 transition"
                    aria-label="Open link"
                  >
                    <ExternalLink size={13} />
                  </button>
                )}
              </div>
            </div>

            {isExpanded && item.pdf_preview_url && (
              <div className="border-t border-paper-100 bg-paper-50 px-3 pb-3 pt-2">
                <p className="text-[10px] font-semibold text-paper-500 mb-2">PDF preview</p>
                <div className="w-full rounded-lg border border-paper-200 overflow-hidden bg-white">
                  <iframe
                    title={`Preview: ${item.title}`}
                    src={item.pdf_preview_url}
                    className="w-full h-64 md:h-80 bg-white block"
                  />
                </div>
              </div>
            )}

            {isAdded && (
              <div className="px-3 pb-2 border-t border-paper-50">
                <span className="text-[10px] font-semibold text-sage-600 bg-sage-100 px-2 py-0.5 rounded-full">
                  {item.in_list ? 'On your list' : 'Added'}
                </span>
              </div>
            )}
          </div>
        )
      })}

      {addable.length > 0 && (
        <button
          type="button"
          onClick={handleAddSelected}
          disabled={loading || selectedAddable.length === 0}
          className={`w-full flex items-center justify-center gap-2 text-sm font-semibold py-3 rounded-xl transition min-h-[48px] touch-manipulation active:scale-[0.99] ${
            selectedAddable.length > 0
              ? 'bg-accent-400 text-white shadow-card hover:bg-accent-500'
              : 'bg-paper-100 text-paper-400 cursor-not-allowed'
          }`}
        >
          {loading ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Saving…
            </>
          ) : (
            <>
              <BookMarked size={14} />
              {selectedAddable.length > 0
                ? `Add ${selectedAddable.length} to reading list`
                : 'Select items to add'}
            </>
          )}
        </button>
      )}

      {error && <p className="text-[11px] text-rust-500 px-1">{error}</p>}
    </div>
  )
}
