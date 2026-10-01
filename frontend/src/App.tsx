import { useEffect, useRef, useState } from 'react'
import { MessageCircle, X, Scroll, Settings, History, Brain } from 'lucide-react'
import { Sidebar } from '@/components/Sidebar'
import { SetupBanner } from '@/components/SetupBanner'
import { MessageBubble } from '@/components/MessageBubble'
import { useChat } from '@/hooks/useChat'
import { useVoiceCall } from '@/hooks/useVoiceCall'
import { ChatInput } from '@/components/ChatInput'
import { VoiceCallBar } from '@/components/VoiceCallBar'
import { ReadingList } from '@/components/ReadingList'
import { Agenda } from '@/components/Agenda'
import FinanceDashboard from '@/components/FinanceDashboard'
import { SettingsView } from '@/components/SettingsView'
import { RecentChats } from '@/components/RecentChats'
import { BrandHeader } from '@/components/BrandHeader'
import { getMorningBriefLatest } from '@/lib/api'
import { isVoiceRepliesEnabled, speakReply } from '@/lib/voice'
import { CAPTURE_HINTS } from '@/agents'
import type { AppView, Attachment } from '@/types'

type View = AppView

// ── Morning Brief Banner ──────────────────────────────────────────────────────
function BriefBanner({ content, onDismiss }: { content: string; onDismiss: () => void }) {
  const lines = content.split('\n').filter(Boolean).slice(0, 4)
  return (
    <div className="bg-white border border-paper-200 rounded-2xl p-4 mb-4 relative shadow-card">
      <button
        onClick={onDismiss}
        className="absolute top-2 right-2 touch-target flex items-center justify-center rounded-full bg-paper-100 active:bg-paper-200 transition text-paper-600"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
      <div className="flex items-center gap-2 mb-2 pr-8">
        <div className="w-6 h-6 rounded-full bg-paper-800 flex items-center justify-center">
          <Scroll size={12} className="text-paper-50" />
        </div>
        <span className="text-[10px] font-bold text-paper-500 tracking-widest uppercase">
          Morning brief
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
}: {
  onSend: (msg: string) => void
}) {
  return (
    <div className="py-10 md:py-16 px-2 flex flex-col items-center text-center">
      <div className="w-14 h-14 rounded-2xl bg-paper-800 text-paper-50 flex items-center justify-center mb-4">
        <Brain size={28} strokeWidth={1.5} />
      </div>
      <h1 className="text-xl md:text-2xl font-semibold text-paper-800 tracking-tight">
        Second Brain
      </h1>
      <p className="mt-2 text-sm text-paper-500 max-w-sm leading-relaxed">
        One chat, one vault. Talk, or start with “remember this…” to append today’s daily note in Inbox.
      </p>
      <p className="mt-2 text-[11px] text-paper-400 font-mono">
        00-Inbox/Daily
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {CAPTURE_HINTS.map(({ label, prompt }) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onSend(prompt)}
            className="px-3.5 py-2 text-sm font-medium text-paper-700 bg-white border border-paper-200 rounded-xl shadow-card active:bg-paper-100 min-h-[44px]"
          >
            {label}
          </button>
        ))}
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
    : view === 'finance' ? 'Finance'
    : view === 'settings' ? 'Settings'
    : null
  return (
    <header className="md:hidden shrink-0 bg-white/95 backdrop-blur-md border-b border-paper-200 flex items-center justify-between px-4 py-2 pt-safe min-h-[48px] sticky top-0 z-20">
      <BrandHeader compact onLogoClick={onLogoClick} />
      <div className="flex items-center gap-2">
        {view === 'chat' && (
          <button
            type="button"
            onClick={onToggleHistory}
            className={`touch-target flex items-center justify-center rounded-full transition ${
              showHistory
                ? 'bg-paper-200 text-paper-800'
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
    { id: 'chat',     icon: <MessageCircle size={20} />, label: 'Chat'     },
    { id: 'settings', icon: <Settings size={20} />,      label: 'Settings' },
  ]
  return (
    <nav className="md:hidden shrink-0 bg-white/95 backdrop-blur-md border-t border-paper-200 flex pb-safe">
      {tabs.map(({ id, icon, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`flex-1 flex flex-col items-center justify-center gap-0.5 pt-1.5 pb-1 text-[10px] font-medium transition min-h-[52px] active:scale-95 touch-manipulation ${
            view === id ? 'text-paper-800' : 'text-paper-400'
          }`}
        >
          <span className={`transition ${view === id ? 'text-paper-800' : 'text-paper-400'}`}>
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
  const voice = useVoiceCall(send)
  const scrollRef = useRef<HTMLDivElement>(null)
  const prevMessageCountRef = useRef(0)
  const spokenIdRef = useRef<string | null>(null)
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

  useEffect(() => {
    if (loading || sending) return
    const last = messages[messages.length - 1]
    if (!last || last.role !== 'assistant' || last.status !== 'complete' || !last.content) return
    if (spokenIdRef.current === last.id) return
    if (voice.active) return
    if (!isVoiceRepliesEnabled()) return
    spokenIdRef.current = last.id
    void speakReply(last.content, last.intent)
  }, [messages, loading, sending, voice.active])

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
    voice.hangup()
    newChat()
    setShowMobileHistory(false)
    setView('chat')
    prevMessageCountRef.current = 0
    spokenIdRef.current = null
  }

  return (
    <div className="h-[100dvh] min-h-0 flex overflow-hidden bg-paper-50 relative">
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
                <SetupBanner onGoToSettings={() => setView('settings')} />
                {showBanner && (
                  <BriefBanner
                    content={briefContent}
                    onDismiss={() => setBriefDismissed(true)}
                  />
                )}
                {messages.length === 0 ? (
                  <EmptyState onSend={handleSend} />
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
            <div className="shrink-0 bg-paper-50/95 border-t border-paper-200 px-3 md:px-5 py-2 md:py-3 backdrop-blur-sm">
              <div className="max-w-2xl mx-auto">
                {voice.active && (
                  <VoiceCallBar
                    phase={voice.phase}
                    level={voice.level}
                    error={voice.error}
                    onHangup={voice.hangup}
                    onTap={voice.endUtterance}
                  />
                )}
                <ChatInput
                  onSend={handleSend}
                  disabled={sending && !voice.active}
                  voice={{
                    active: voice.active,
                    phase: voice.phase,
                    onToggle: voice.toggle,
                  }}
                />
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
        ) : view === 'finance' ? (
          <div className="flex-1 overflow-hidden">
            <FinanceDashboard />
          </div>
        ) : (
          <div className="flex-1 overflow-hidden">
            <SettingsView onOpenView={setView} />
          </div>
        )}

        {/* Mobile bottom nav */}
        <BottomNav view={view} onChange={setView} />
      </div>
    </div>
  )
}

export default App
