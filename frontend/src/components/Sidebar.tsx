import { MessageCircle, BookOpen, Settings, CalendarDays, DollarSign, Inbox, Utensils } from 'lucide-react'
import { BrandHeader } from '@/components/BrandHeader'
import { RecentChats } from '@/components/RecentChats'
import type { AppView, ChatSessionSummary } from '@/types'

type View = AppView

interface Props {
  activeView: View
  onViewChange: (v: View) => void
  sessions: ChatSessionSummary[]
  activeSessionId: string | null
  onSelectSession: (id: string) => void
  onNewChat: () => void
  reviewCount?: number
}

export function Sidebar({
  activeView,
  onViewChange,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  reviewCount = 0,
}: Props) {
  return (
    <aside className="hidden md:flex flex-col w-72 shrink-0 bg-paper-50/95 border-r border-paper-200 h-full overflow-y-auto backdrop-blur-sm">

      <div className="px-4 pt-5 pb-4 border-b border-paper-200 shrink-0">
        <BrandHeader onLogoClick={onNewChat} />
      </div>

      <nav className="px-3 pt-3 pb-2 space-y-1 border-b border-paper-200 shrink-0">
        {(
          [
            { id: 'chat' as View, icon: <MessageCircle size={16} />, label: 'Chat' },
            { id: 'nutrition' as View, icon: <Utensils size={16} />, label: 'Nutrition' },
            { id: 'review' as View, icon: <Inbox size={16} />, label: 'Review' },
            { id: 'settings' as View, icon: <Settings size={16} />, label: 'Settings' },
          ] as const
        ).map(({ id, icon, label }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl transition text-left ${
              activeView === id
                ? 'bg-paper-100 text-accent-400'
                : 'text-paper-500 hover:bg-paper-100 hover:text-paper-700'
            }`}
          >
            <span className={activeView === id ? 'text-accent-400' : 'text-paper-400'}>{icon}</span>
            <span className="text-sm font-medium">{label}</span>
            {id === 'review' && reviewCount > 0 && (
              <span className="ml-auto text-[10px] font-semibold bg-paper-200 text-paper-700 rounded-full px-1.5 py-0.5">
                {reviewCount}
              </span>
            )}
            {id !== 'review' && activeView === id && (
              <div className="ml-auto w-1.5 h-1.5 rounded-full bg-accent-400" />
            )}
          </button>
        ))}
      </nav>

      {activeView === 'chat' && (
        <div className="px-3 py-3 border-b border-paper-200 shrink-0">
          <RecentChats
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelectSession={(id) => {
              onSelectSession(id)
              onViewChange('chat')
            }}
            onNewChat={onNewChat}
          />
        </div>
      )}

      <div className="flex-1 px-3 py-3 overflow-y-auto">
        <p className="text-[10px] font-bold text-paper-400 uppercase tracking-widest px-1 mb-1">
          More
        </p>
        {(
          [
            { id: 'reading' as View, icon: <BookOpen size={15} />, label: 'Reading list' },
            { id: 'agenda' as View, icon: <CalendarDays size={15} />, label: 'Agenda' },
            { id: 'finance' as View, icon: <DollarSign size={15} />, label: 'Finance' },
          ] as const
        ).map(({ id, icon, label }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg transition text-left ${
              activeView === id
                ? 'bg-paper-100 text-paper-700'
                : 'text-paper-400 hover:bg-paper-50 hover:text-paper-600'
            }`}
          >
            <span>{icon}</span>
            <span className="text-xs font-medium">{label}</span>
          </button>
        ))}
      </div>
    </aside>
  )
}
