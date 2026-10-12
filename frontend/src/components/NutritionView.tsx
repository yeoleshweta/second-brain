import { useEffect, useState } from 'react'
import { listRecipes } from '@/lib/api'
import { splitLinks } from '@/lib/linkify'
import { openExternalUrl } from '@/lib/openExternal'
import type { SavedRecipe } from '@/types'

export function NutritionView() {
  const [recipes, setRecipes] = useState<SavedRecipe[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    listRecipes()
      .then((data) => {
        if (!cancelled) setRecipes(data.recipes ?? [])
      })
      .catch(() => {
        if (!cancelled) setError('Could not load recipes.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="h-full overflow-y-auto mobile-scroll">
      <div className="max-w-[720px] mx-auto px-4 py-4 space-y-3">
        <h2 className="text-sm font-semibold text-void-text">Nutrition</h2>
        <p className="text-xs text-void-muted leading-relaxed">
          Personal recipes and YouTube links you save. Ask in chat, “what’s my dal recipe”, and it reads this list.
        </p>
        {loading && <p className="text-sm text-void-muted">Loading recipes…</p>}
        {error && <p className="text-sm text-void-static">{error}</p>}
        {!loading && !error && recipes.length === 0 && (
          <div className="rounded-2xl border border-white/10 bg-void-surface/70 p-4">
            <p className="text-sm text-void-text">No recipes yet.</p>
            <p className="mt-2 text-xs text-void-muted leading-relaxed">
              Say “remember this recipe” and the steps, or share a YouTube link from your phone.
            </p>
          </div>
        )}
        {recipes.map((item) => (
          <article
            key={`${item.path}-${item.time}-${item.title}`}
            className="rounded-2xl border border-white/10 bg-void-surface/70 p-4 min-w-0"
          >
            <p className="text-[11px] uppercase tracking-wide text-void-muted">
              {item.kind === 'youtube' ? 'YouTube' : 'Personal'} · {item.date} {item.time}
            </p>
            <h3 className="mt-1 text-base text-void-text break-words">{item.title || 'Recipe'}</h3>
            {item.kind === 'personal' && (
              <p className="mt-2 text-sm text-void-text leading-relaxed whitespace-pre-wrap break-words">
                {splitLinks(item.body).map((part, index) =>
                  part.kind === 'link' ? (
                    <button
                      key={`${part.value}-${index}`}
                      type="button"
                      className="text-void-red underline underline-offset-2 break-all text-left"
                      onClick={() => openExternalUrl(part.value)}
                    >
                      {part.value}
                    </button>
                  ) : (
                    <span key={`${index}-t`}>{part.value}</span>
                  ),
                )}
              </p>
            )}
            {item.url && (
              <button
                type="button"
                className="mt-3 min-h-[44px] text-sm text-void-red underline underline-offset-2 break-all text-left"
                onClick={() => openExternalUrl(item.url)}
              >
                {item.url}
              </button>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}
