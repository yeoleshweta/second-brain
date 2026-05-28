import { useCallback, useEffect, useState } from 'react'
import { usePlaidLink } from 'react-plaid-link'
import { Brain, Link2, Check, AlertCircle, MessageCircle, BookOpen, Menu, X } from 'lucide-react'
import { getPlaidLinkToken, plaidExchange } from '@/lib/api'

type View = 'chat' | 'reading'

interface SidebarProps {
  activeView: View
  onViewChange: (view: View) => void
}

export function Sidebar({ activeView, onViewChange }: SidebarProps) {
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [linkError, setLinkError] = useState<string | null>(null)
  const [linkedItems, setLinkedItems] = useState<number>(0)
  const [mobileOpen, setMobileOpen] = useState(false)

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
      setLinkToken(null)
    } catch (err) {
      setLinkError((err as Error).message)
    }
  }, [])

  const { open, ready } = usePlaidLink({ token: linkToken, onSuccess })

  useEffect(() => {
    if (linkToken && ready) open()
  }, [linkToken, ready, open])

  const navItems: { view: View; label: string; icon: React.ReactNode }[] = [
    { view: 'chat', label: 'Chat', icon: <MessageCircle size={16} /> },
    { view: 'reading', label: '📚 Reading List', icon: <BookOpen size={16} /> },
  ]

  const sidebarContent = (
    <aside className="w-full md:w-64 bg-ink-800 border-r border-ink-700 flex flex-col h-full">
      <div className="p-4 border-b border-ink-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="text-blue-400" size={22} />
          <h1 className="font-semibold text-ink-100">Second Brain</h1>
        </div>
        <button
          className="md:hidden text-ink-400 hover:text-ink-200"
          onClick={() => setMobileOpen(false)}
        >
          <X size={20} />
        </button>
      </div>

      <div className="p-4 flex-1 space-y-4 text-sm overflow-y-auto">
        {/* Navigation */}
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-400 mb-2">Views</div>
          <ul className="space-y-1">
            {navItems.map(({ view, label, icon }) => (
              <li key={view}>
                <button
                  onClick={() => {
                    onViewChange(view)
                    setMobileOpen(false)
                  }}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition ${
                    activeView === view
                      ? 'bg-blue-600 text-white'
                      : 'text-ink-200 hover:bg-ink-700'
                  }`}
                >
                  {icon}
                  {label}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Agents */}
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-400 mb-2">Agents</div>
          <ul className="space-y-1 text-ink-200">
            <li className="flex items-center justify-between px-3 py-1.5">
              <span>🪄 Ross</span>
              <span className="text-xs text-emerald-500">active</span>
            </li>
            <li className="flex items-center justify-between px-3 py-1.5">
              <span>🥗 Health</span>
              <span className="text-xs text-ink-500">stub</span>
            </li>
            <li className="flex items-center justify-between px-3 py-1.5">
              <span>💰 Finance</span>
              <span className="text-xs text-ink-500">stub</span>
            </li>
            <li className="flex items-center justify-between px-3 py-1.5">
              <span>📅 Calendar</span>
              <span className="text-xs text-ink-500">stub</span>
            </li>
          </ul>
        </div>

        {/* Connections */}
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-400 mb-2">Connections</div>
          <button
            onClick={fetchToken}
            className="w-full flex items-center gap-2 px-3 py-2 bg-ink-700 hover:bg-ink-600 rounded-md text-ink-100 transition min-h-[44px]"
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

      <div className="p-4 border-t border-ink-700 text-xs text-ink-500">Local only · v0.1</div>
    </aside>
  )

  return (
    <>
      {/* Mobile hamburger */}
      <button
        className="md:hidden fixed top-3 left-3 z-40 bg-ink-800 border border-ink-700 rounded-lg p-2 text-ink-300 min-h-[44px] min-w-[44px] flex items-center justify-center"
        onClick={() => setMobileOpen(true)}
      >
        <Menu size={20} />
      </button>

      {/* Desktop sidebar */}
      <div className="hidden md:flex w-64 shrink-0">{sidebarContent}</div>

      {/* Mobile slide-over */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="w-72 max-w-[85vw] flex flex-col">{sidebarContent}</div>
          <div
            className="flex-1 bg-black/50"
            onClick={() => setMobileOpen(false)}
          />
        </div>
      )}
    </>
  )
}
