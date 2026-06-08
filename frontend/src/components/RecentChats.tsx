import { History, Plus } from 'lucide-react'
import type { ChatSessionSummary } from '@/types'

interface Props {
  sessions: ChatSessionSummary[]
  activeSessionId: string | null
  onSelectSession: (id: string) => void
  onNewChat: () => void
  compact?: boolean
}

function formatWhen(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  if (sameDay) {
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

export function RecentChats({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  compact = false,
}: Props) {
  return (
    <div className={compact ? 'space-y-2' : 'space-y-2 px-1'}>
      <div className="flex items-center justify-between gap-2 px-1">
        <p className="text-[10px] font-bold text-friends-purple uppercase tracking-widest flex items-center gap-1">
          <History size={11} />
          Recent chats
        </p>
        <button
          type="button"
          onClick={onNewChat}
          className="flex items-center gap-1 text-[10px] font-semibold text-friends-sofa hover:text-friends-purple transition min-h-[32px] px-2 rounded-lg hover:bg-paper-50"
        >
          <Plus size={12} />
          New
        </button>
      </div>

      {sessions.length === 0 ? (
        <p className="text-[11px] text-paper-400 px-2 py-1 italic">
          No past chats yet — say hi to Ross!
        </p>
      ) : (
        <div className={`space-y-1 ${compact ? 'max-h-48 overflow-y-auto' : ''}`}>
          {sessions.map((session) => {
            const active = session.id === activeSessionId
            return (
              <button
                key={session.id}
                type="button"
                onClick={() => onSelectSession(session.id)}
                className={`w-full text-left rounded-xl px-3 py-2.5 transition min-h-[44px] border ${
                  active
                    ? 'bg-friends-frame/25 border-friends-frame/80 text-friends-purple-dark'
                    : 'bg-white/70 border-paper-100 text-paper-600 hover:bg-paper-50 hover:border-paper-200'
                }`}
              >
                <p className="text-xs font-semibold truncate leading-snug">{session.title}</p>
                <p className="text-[10px] text-paper-400 mt-0.5">
                  {formatWhen(session.updated_at)}
                  {session.message_count > 0 ? ` · ${session.message_count} msgs` : ''}
                </p>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
