import { useEffect, useRef, useState } from 'react'
import { MessageCircle, BookOpen, X, Scroll, Settings, History, CalendarDays } from 'lucide-react'
import { Sidebar } from '@/components/Sidebar'
import { MessageBubble } from '@/components/MessageBubble'
import { ChatInput } from '@/components/ChatInput'
import { ReadingList } from '@/components/ReadingList'
import { Agenda } from '@/components/Agenda'
import { SettingsView } from '@/components/SettingsView'
import { RecentChats } from '@/components/RecentChats'
import { FriendsBackground, FriendsDoorHeader } from '@/components/friends/FriendsDecor'
import { FriendsHomescreenGrid, FriendAppIcon } from '@/components/friends/FriendsHomescreen'
import { CharacterAvatarByAgentId } from '@/components/friends/CharacterAvatar'
import { useChat } from '@/hooks/useChat'
import { getMorningBriefLatest } from '@/lib/api'
import type { AgentDef } from '@/agents'
import { AGENTS } from '@/agents'
import type { AppView, Attachment } from '@/types'

type View = AppView

// ── Morning Brief Banner ──────────────────────────────────────────────────────
function BriefBanner({ content, onDismiss }: { content: string; onDismiss: () => void }) {
  const lines = content.split('\n').filter(Boolean).slice(0, 4)
  return (
    <div className="bg-gradient-to-br from-friends-frame/40 to-gold-100 border-2 border-friends-frame rounded-2xl p-4 mb-4 relative shadow-card">
      <button
        onClick={onDismiss}
        className="absolute top-2 right-2 touch-target flex items-center justify-center rounded-full bg-paper-200 active:bg-paper-300 transition text-paper-600"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
      <div className="flex items-center gap-2 mb-2 pr-8">
        <div className="w-6 h-6 rounded-full bg-gold-400 flex items-center justify-center">
          <Scroll size={12} className="text-white" />
        </div>
        <span className="text-[10px] font-bold text-friends-purple-dark tracking-widest uppercase">
          centralperk brief
        </span>
      </div>
      {lines.map((l, i) => (
        <p key={i} className="text-xs text-paper-600 leading-relaxed truncate">{l}</p>
      ))}
    </div>
  )
}

// ── Empty / intro state ───────────────────────────────────────────────────────
function EmptyState({
  onSend,
  onNewChat,
}: {
  onSend: (msg: string) => void
  onNewChat?: () => void
}) {
  const liveAgents = AGENTS.filter((a) => a.live)
  const futureAgents = AGENTS.filter((a) => !a.live)

  function handleAgentTap(agent: AgentDef) {
    const first = agent.suggestions[0]
    if (first) onSend(first.prompt)
  }

  return (
    <div className="py-3 md:py-4 px-1 space-y-4 md:space-y-5">

      {/* Hero: animated couch logo + homescreen grid */}
      <div className="space-y-3 md:space-y-4">
        <FriendsDoorHeader hero onLogoClick={onNewChat} />
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl md:rounded-3xl border border-friends-frame/50 shadow-card p-3 md:p-4">
          <p className="text-[10px] font-bold text-friends-purple uppercase tracking-widest text-center mb-2 md:mb-3">
            Tap a friend on the couch
          </p>
          <FriendsHomescreenGrid onAgentTap={handleAgentTap} />
          <p className="text-xs text-paper-500 text-center mt-3 md:mt-4 leading-relaxed">
            Ross & Monica are live — everyone else pulls up a chair soon.
          </p>
        </div>
      </div>

      {/* Mobile: quick Ross prompts (compact) */}
      {liveAgents.length > 0 && (
        <div className="md:hidden space-y-2">
          <p className="text-[10px] font-bold text-paper-400 uppercase tracking-widest px-1">
            Try asking Ross
          </p>
          {liveAgents[0].suggestions.map(({ label, prompt }) => (
            <button
              key={prompt}
              onClick={() => onSend(prompt)}
              className="w-full flex items-center justify-between bg-white active:bg-paper-100 border border-paper-200 rounded-xl px-4 py-3.5 text-left transition min-h-[48px] shadow-card"
            >
              <span className="text-sm font-semibold text-paper-700">{label}</span>
              <span className="text-paper-300 text-lg leading-none ml-2 shrink-0">›</span>
            </button>
          ))}
        </div>
      )}

      {/* Desktop: full agent cards with suggestions */}
      <div className="hidden md:block space-y-3">
        <p className="text-[10px] font-bold text-paper-400 uppercase tracking-widest px-1">
          Online now
        </p>
        {liveAgents.map((agent) => (
          <div key={agent.id} className="bg-white rounded-2xl border border-paper-200 shadow-card overflow-hidden">
            <div className="flex items-center gap-3 px-4 pt-3.5 pb-2">
              <CharacterAvatarByAgentId agentId={agent.id} size="md" framed />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-sm font-bold text-paper-800">{agent.name}</span>
                  <span className="flex items-center gap-1 text-[9px] font-bold text-friends-awning bg-sage-100 px-1.5 py-0.5 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-friends-awning inline-block animate-pulse" />
                    AT CENTRAL PERK
                  </span>
                </div>
                <p className="text-[10px] text-paper-500 font-medium mt-0.5">{agent.specialty}</p>
                <p className="text-[10px] text-friends-purple italic leading-snug">&ldquo;{agent.catchphrase}&rdquo;</p>
              </div>
            </div>
            <div className="px-3 pb-3 space-y-1.5">
              {agent.suggestions.map(({ label, prompt }) => (
                <button
                  key={prompt}
                  onClick={() => onSend(prompt)}
                  className="w-full flex items-center justify-between bg-paper-50 hover:bg-paper-100 active:bg-paper-200 border border-paper-200 rounded-xl px-3.5 py-2.5 text-left transition group min-h-[44px]"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-paper-700 group-hover:text-paper-900 leading-none mb-0.5">
                      {label}
                    </p>
                    <p className="text-[10px] text-paper-400 truncate max-w-[220px]">{prompt}</p>
                  </div>
                  <span className="text-paper-300 group-hover:text-accent-400 transition text-lg leading-none ml-2 shrink-0">›</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Coming-soon as a grid of small cards — desktop only */}
      <div className="hidden md:block space-y-2">
        <p className="text-[10px] font-bold text-paper-400 uppercase tracking-widest px-1">
          Coming soon
        </p>
        <div className="grid grid-cols-3 gap-3">
          {futureAgents.map((agent) => (
            <div key={agent.id} className="flex flex-col items-center opacity-55">
              <FriendAppIcon agent={agent} dimmed />
              <span className="text-[9px] font-bold text-paper-400 bg-paper-100 px-2 py-0.5 rounded-full mt-1">
                Phase {agent.phase}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Mobile header ─────────────────────────────────────────────────────────────
function MobileHeader({
  view,
  showHistory,
  onToggleHistory,
  onLogoClick,
}: {
  view: View
  showHistory: boolean
  onToggleHistory: () => void
  onLogoClick: () => void
}) {
  const label =
    view === 'reading' ? 'Reading'
    : view === 'agenda' ? 'Agenda'
    : view === 'settings' ? 'Settings'
    : null
  return (
    <header className="md:hidden shrink-0 bg-white/95 backdrop-blur-md border-b border-paper-200 flex items-center justify-between px-4 py-2 pt-safe min-h-[48px] sticky top-0 z-20">
      <FriendsDoorHeader compact onLogoClick={onLogoClick} />
      <div className="flex items-center gap-2">
        {view === 'chat' && (
          <button
            type="button"
            onClick={onToggleHistory}
            className={`touch-target flex items-center justify-center rounded-full transition ${
              showHistory
                ? 'bg-friends-frame/40 text-friends-purple'
                : 'bg-paper-100 text-paper-500 active:bg-paper-200'
            }`}
            aria-label="Recent chats"
          >
            <History size={18} />
          </button>
        )}
        {label && (
          <span className="text-xs font-semibold text-paper-500">{label}</span>
        )}
      </div>
    </header>
  )
}

// ── Bottom nav (mobile) ───────────────────────────────────────────────────────
function BottomNav({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  const tabs: { id: View; icon: React.ReactNode; label: string }[] = [
    { id: 'chat',    icon: <MessageCircle size={24} />, label: 'Chat'    },
    { id: 'reading', icon: <BookOpen size={24} />,       label: 'Reading' },
    { id: 'agenda',  icon: <CalendarDays size={24} />,   label: 'Agenda'  },
    { id: 'settings', icon: <Settings size={24} />,      label: 'Settings' },
  ]
  return (
    <nav className="md:hidden shrink-0 bg-white/95 backdrop-blur-md border-t border-paper-200 flex pb-safe">
      {tabs.map(({ id, icon, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`flex-1 flex flex-col items-center justify-center gap-0.5 pt-2 pb-1.5 text-xs font-medium transition min-h-[56px] active:scale-95 touch-manipulation ${
            view === id ? 'text-friends-purple' : 'text-paper-400'
          }`}
        >
          <span className={`transition ${view === id ? 'text-friends-sofa' : 'text-paper-400'}`}>
            {icon}
          </span>
          {label}
        </button>
      ))}
    </nav>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────
function App() {
  const [view, setView] = useState<View>('chat')
  const [showMobileHistory, setShowMobileHistory] = useState(false)
  const {
    messages,
    sending,
    loading,
    send,
    sessionId,
    sessions,
    loadSession,
    newChat,
  } = useChat()
  const scrollRef = useRef<HTMLDivElement>(null)
  const prevMessageCountRef = useRef(0)
  const [briefContent, setBriefContent] = useState<string | null>(null)
  const [briefDismissed, setBriefDismissed] = useState(false)

  // Auto-scroll on new messages
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const previousCount = prevMessageCountRef.current

    // When transitioning from the empty state to active chat, force to bottom.
    if (previousCount === 0 && messages.length > 0) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'auto' })
      prevMessageCountRef.current = messages.length
      return
    }

    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 200
    if (nearBottom || messages[messages.length - 1]?.role === 'user') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
    prevMessageCountRef.current = messages.length
  }, [messages])

  // Load morning brief once
  useEffect(() => {
    getMorningBriefLatest()
      .then((d) => { if (d.content) setBriefContent(d.content) })
      .catch(() => {})
  }, [])

  // Keep chat scrolled when iOS keyboard opens
  useEffect(() => {
    if (view !== 'chat') return
    const vv = window.visualViewport
    if (!vv) return
    const handler = () => {
      const el = scrollRef.current
      if (el) el.scrollTop = el.scrollHeight
    }
    vv.addEventListener('resize', handler)
    return () => vv.removeEventListener('resize', handler)
  }, [view, messages.length])

  const showBanner = briefContent && !briefDismissed && view === 'chat'
  const handleSend = (text: string, attachments: Attachment[] = []) => {
    setShowMobileHistory(false)
    send(text, attachments)
  }

  const handleSelectSession = (id: string) => {
    setShowMobileHistory(false)
    void loadSession(id)
    setView('chat')
  }

  const handleNewChat = () => {
    newChat()
    setShowMobileHistory(false)
    setView('chat')
    prevMessageCountRef.current = 0
  }

  return (
    <div className="h-[100dvh] min-h-0 flex overflow-hidden bg-friends-cream relative">
      <FriendsBackground />
      {/* Desktop sidebar */}
      <Sidebar
        activeView={view}
        onViewChange={setView}
        sessions={sessions}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
      />

      {/* Main column */}
      <div className="flex-1 min-h-0 flex flex-col min-w-0 overflow-hidden">

        <MobileHeader
          view={view}
          showHistory={showMobileHistory}
          onToggleHistory={() => setShowMobileHistory((v) => !v)}
          onLogoClick={handleNewChat}
        />

        {/* View content */}
        {view === 'chat' ? (
          <>
            {showMobileHistory && (
              <div className="md:hidden shrink-0 border-b border-paper-200 bg-white/95 px-3 py-3 backdrop-blur-sm">
                <RecentChats
                  sessions={sessions}
                  activeSessionId={sessionId}
                  onSelectSession={handleSelectSession}
                  onNewChat={handleNewChat}
                  compact
                />
              </div>
            )}
            {/* Scrollable messages */}
            <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto mobile-scroll">
              <div className="max-w-2xl mx-auto px-3 md:px-5 py-3 md:py-4 pb-6">
                {loading ? (
                  <p className="text-sm text-paper-400 text-center py-8">Loading your chats…</p>
                ) : (
                  <>
                {showBanner && (
                  <BriefBanner
                    content={briefContent}
                    onDismiss={() => setBriefDismissed(true)}
                  />
                )}
                {messages.length === 0 ? (
                  <EmptyState onSend={handleSend} onNewChat={handleNewChat} />
                ) : (
                  <div className="space-y-1 pb-2">
                    {messages.map((m) => (
                      <MessageBubble key={m.id} message={m} />
                    ))}
                  </div>
                )}
                  </>
                )}
              </div>
            </div>

            {/* Chat input — sits above bottom nav */}
            <div className="shrink-0 bg-friends-cream/95 border-t border-friends-frame/50 px-3 md:px-5 py-2 md:py-3 backdrop-blur-sm">
              <div className="max-w-2xl mx-auto">
                <ChatInput onSend={handleSend} disabled={sending} />
              </div>
            </div>
          </>
        ) : view === 'reading' ? (
          <div className="flex-1 overflow-hidden">
            <ReadingList />
          </div>
        ) : view === 'agenda' ? (
          <div className="flex-1 overflow-hidden">
            <Agenda />
          </div>
        ) : (
          <div className="flex-1 overflow-hidden">
            <SettingsView />
          </div>
        )}

        {/* Mobile bottom nav */}
        <BottomNav view={view} onChange={setView} />
      </div>
    </div>
  )
}

export default App
