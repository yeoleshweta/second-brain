import { useCallback, useEffect, useState } from 'react'
import { usePlaidLink } from 'react-plaid-link'
import { Brain, Link2, Check, AlertCircle } from 'lucide-react'
import { getPlaidLinkToken, plaidExchange } from '@/lib/api'

export function Sidebar() {
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [linkError, setLinkError] = useState<string | null>(null)
  const [linkedItems, setLinkedItems] = useState<number>(0)

  const fetchToken = useCallback(async () => {
    try {
      setLinkError(null)
      const token = await getPlaidLinkToken()
      setLinkToken(token)
    } catch (err) {
      setLinkError((err as Error).message)
    }
  }, [])

  const onSuccess = useCallback(async (publicToken: string) => {
    try {
      await plaidExchange(publicToken)
      setLinkedItems((n) => n + 1)
      setLinkToken(null) // force re-fetch next time
    } catch (err) {
      setLinkError((err as Error).message)
    }
  }, [])

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess,
  })

  useEffect(() => {
    if (linkToken && ready) {
      open()
    }
  }, [linkToken, ready, open])

  return (
    <aside className="w-64 bg-ink-800 border-r border-ink-700 flex flex-col">
      <div className="p-4 border-b border-ink-700 flex items-center gap-2">
        <Brain className="text-blue-400" size={22} />
        <h1 className="font-semibold text-ink-100">Second Brain</h1>
      </div>

      <div className="p-4 flex-1 space-y-4 text-sm">
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-400 mb-2">Agents</div>
          <ul className="space-y-1 text-ink-200">
            <li className="flex items-center justify-between">
              <span>📚 Knowledge</span>
              <span className="text-xs text-ink-500">stub</span>
            </li>
            <li className="flex items-center justify-between">
              <span>🥗 Health</span>
              <span className="text-xs text-ink-500">stub</span>
            </li>
            <li className="flex items-center justify-between">
              <span>💰 Finance</span>
              <span className="text-xs text-ink-500">stub</span>
            </li>
            <li className="flex items-center justify-between">
              <span>📅 Calendar</span>
              <span className="text-xs text-ink-500">stub</span>
            </li>
          </ul>
        </div>

        <div>
          <div className="text-xs uppercase tracking-wider text-ink-400 mb-2">Connections</div>
          <button
            onClick={fetchToken}
            className="w-full flex items-center gap-2 px-3 py-2 bg-ink-700 hover:bg-ink-600 rounded-md text-ink-100 transition"
          >
            <Link2 size={14} />
            Link bank account
            {linkedItems > 0 && (
              <span className="ml-auto text-xs bg-emerald-700 text-emerald-100 px-1.5 py-0.5 rounded">
                {linkedItems}
              </span>
            )}
          </button>
          {linkedItems > 0 && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-emerald-400">
              <Check size={12} />
              {linkedItems} item{linkedItems > 1 ? 's' : ''} linked
            </div>
          )}
          {linkError && (
            <div className="mt-2 flex items-start gap-1.5 text-xs text-rose-400">
              <AlertCircle size={12} className="mt-0.5 shrink-0" />
              <span className="break-all">{linkError}</span>
            </div>
          )}
        </div>
      </div>

      <div className="p-4 border-t border-ink-700 text-xs text-ink-500">
        Local only · v0.1
      </div>
    </aside>
  )
}
