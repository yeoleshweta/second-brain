import { MessageCircle, BookOpen, Settings, CalendarDays, DollarSign } from 'lucide-react'
import { AGENTS } from '@/agents'
import { CharacterAvatarByAgentId } from '@/components/friends/CharacterAvatar'
import { FriendsDoorHeader } from '@/components/friends/FriendsDecor'
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
}

export function Sidebar({
  activeView,
  onViewChange,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
}: Props) {
  const liveAgents = AGENTS.filter((a) => a.live)
  const futureAgents = AGENTS.filter((a) => !a.live)

  return (
    <aside className="hidden md:flex flex-col w-72 shrink-0 bg-white/95 border-r border-friends-frame/60 h-full overflow-y-auto backdrop-blur-sm">

      <div className="px-4 pt-5 pb-4 border-b border-paper-200 shrink-0">
        <FriendsDoorHeader onLogoClick={onNewChat} />
        <p className="text-[10px] text-paper-400 mt-3 text-center lowercase tracking-wide">
          centralperk · 6 friends on the couch
        </p>
      </div>

      <nav className="px-3 pt-3 pb-2 space-y-1 border-b border-paper-200 shrink-0">
        {(
          [
            { id: 'chat' as View, icon: <MessageCircle size={16} />, label: 'Central Perk Chat' },
            { id: 'reading' as View, icon: <BookOpen size={16} />, label: 'Reading List' },
            { id: 'agenda' as View, icon: <CalendarDays size={16} />, label: 'Chandler Agenda' },
            { id: 'finance' as View, icon: <DollarSign size={16} />, label: 'Finance' },
            { id: 'settings' as View, icon: <Settings size={16} />, label: 'Settings' },
          ] as const
        ).map(({ id, icon, label }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl transition text-left ${
              activeView === id
                ? 'bg-friends-frame/30 text-friends-purple-dark'
                : 'text-paper-500 hover:bg-paper-50 hover:text-paper-700'
            }`}
          >
            <span className={activeView === id ? 'text-friends-sofa' : 'text-paper-400'}>{icon}</span>
            <span className="text-sm font-medium">{label}</span>
            {activeView === id && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-friends-sofa" />}
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

      <div className="flex-1 px-3 py-3 space-y-4 overflow-y-auto">
        <div>
          <p className="text-[10px] font-bold text-friends-purple uppercase tracking-widest px-1 mb-2">
            On the orange couch
          </p>
          <div className="space-y-2">
            {liveAgents.map((agent) => (
              <div
                key={agent.id}
                className="bg-friends-cream rounded-xl border-2 border-friends-frame/80 shadow-card p-3"
              >
                <div className="flex items-start gap-2.5">
                  <CharacterAvatarByAgentId agentId={agent.id} size="md" framed />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="text-sm font-bold text-paper-800">{agent.name}</span>
                      <span className="text-[9px] font-bold text-friends-awning bg-white px-1.5 py-0.5 rounded-full">
                        LIVE
                      </span>
                    </div>
                    <p className="text-[10px] font-semibold text-paper-500 mb-0.5">{agent.specialty}</p>
                    <p className="text-[10px] text-friends-purple italic leading-snug line-clamp-2">
                      &ldquo;{agent.catchphrase}&rdquo;
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="text-[10px] font-bold text-paper-400 uppercase tracking-widest px-1 mb-2">
            Not at the Perk yet
          </p>
          <div className="space-y-2">
            {futureAgents.map((agent) => (
              <div key={agent.id} className="bg-paper-50 rounded-xl border border-paper-100 p-3 opacity-65">
                <div className="flex items-center gap-2.5">
                  <CharacterAvatarByAgentId agentId={agent.id} size="sm" framed={false} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-bold text-paper-700">{agent.name}</span>
                      <span className="text-[9px] font-bold text-paper-400 bg-paper-200 px-1.5 py-0.5 rounded-full">
                        Phase {agent.phase}
                      </span>
                    </div>
                    <p className="text-[10px] text-paper-400 mt-0.5">{agent.specialty}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  )
}
