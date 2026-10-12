import { useEffect, useRef, useState } from 'react'
import { MessageCircle, X, Scroll, Settings, History, Inbox } from 'lucide-react'
import { Sidebar } from '@/components/Sidebar'
import { MessageBubble } from '@/components/MessageBubble'
import { useChat } from '@/hooks/useChat'
import { useVoiceCall } from '@/hooks/useVoiceCall'
import { ChatInput } from '@/components/ChatInput'
import { VoiceCallBar } from '@/components/VoiceCallBar'
import { ReadingList } from '@/components/ReadingList'
import { Agenda } from '@/components/Agenda'
import FinanceDashboard from '@/components/FinanceDashboard'
import { SettingsView } from '@/components/SettingsView'
import { ReviewInbox } from '@/components/ReviewInbox'
import { RecentChats } from '@/components/RecentChats'
import { VoidWordmark } from '@/components/BrandHeader'
import { getMorningBriefLatest, listWikiPending } from '@/lib/api'
import { isPlainMode, isVoiceRepliesEnabled, speakReply } from '@/lib/voice'
import type { AppView, Attachment } from '@/types'

type View = AppView

// ── Morning Brief Banner ──────────────────────────────────────────────────────
function BriefBanner({ content, onDismiss }: { content: string; onDismiss: () => void }) {
  const lines = content.split('\n').filter(Boolean).slice(0, 4)
  return (
    <div className="bg-paper-50 border border-paper-200 rounded-2xl p-4 mb-4 relative shadow-card">
      <button
        onClick={onDismiss}
        className="absolute top-2 right-2 touch-target flex items-center justify-center rounded-full bg-paper-100 active:bg-paper-200 transition text-paper-600"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
      <div className="flex items-center gap-2 mb-2 pr-8">
        <div className="w-6 h-6 rounded-full bg-accent-500 flex items-center justify-center">
          <Scroll size={12} className="text-white" />
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
function EmptyState() {
  return (
    <div className="py-16 px-6 flex flex-col items-center text-center">
      <h1><VoidWordmark className="h-14 w-[280px]" /></h1>
      {!isPlainMode() && (
        <p className="mt-6 text-sm italic text-void-muted">Quiet out there tonight.</p>
      )}
      <p className="mt-2 text-xs text-void-muted">Say ‘remember this’ to keep something.</p>
    </div>
  )
}

// ── Mobile header ─────────────────────────────────────────────────────────────
function MobileHeader({
  view,
  showHistory,
  unsortedCount,
  onToggleHistory,
  onOpenSettings,
  onOpenUnsorted,
  onLogoClick,
}: {
  view: View
  showHistory: boolean
  unsortedCount: number
  onToggleHistory: () => void
  onOpenSettings: () => void
  onOpenUnsorted: () => void
  onLogoClick: () => void
}) {
  const label =
    view === 'reading' ? 'Reading'
    : view === 'agenda' ? 'Agenda'
    : view === 'finance' ? 'Finance'
    : view === 'settings' ? 'Settings'
    : view === 'review' ? 'Review'
    : null
  return (
    <header className="md:hidden relative shrink-0 bg-transparent flex items-center justify-between px-2 py-2 pt-safe min-h-[52px] sticky top-0 z-20">
      <button
        type="button"
        onClick={onOpenSettings}
        className="touch-target flex items-center justify-center rounded-full text-void-text"
        aria-label="Settings"
      >
        <Settings size={20} />
      </button>
      {view === 'chat' ? (
        <button
          type="button"
          onClick={onLogoClick}
          className="absolute left-1/2 -translate-x-1/2"
          aria-label="Start new chat"
        >
          <VoidWordmark className="h-7 w-[168px]" />
        </button>
      ) : (
        <span className="absolute left-1/2 -translate-x-1/2 text-sm font-medium text-void-muted">{label}</span>
      )}
      <div className="flex items-center">
        {view === 'chat' && (
          <button
            type="button"
            onClick={onToggleHistory}
            className={`touch-target flex items-center justify-center rounded-full ${
              showHistory ? 'text-void-text' : 'text-void-muted'
            }`}
            aria-label="Recent chats"
          >
            <History size={18} />
          </button>
        )}
        <button
          type="button"
          onClick={onOpenUnsorted}
          className="touch-target inline-flex items-center justify-center"
          aria-label={`${unsortedCount} unsorted`}
        >
          <span className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full border border-void-upside text-sm text-void-text">
            <span className="w-2 h-2 rounded-full bg-void-upside" aria-hidden />
            {unsortedCount}
          </span>
        </button>
      </div>
    </header>
  )
}

// ── Bottom nav (mobile) ───────────────────────────────────────────────────────
function BottomNav({
  view,
  onChange,
  reviewCount = 0,
}: {
  view: View
  onChange: (v: View) => void
  reviewCount?: number
}) {
  const tabs: { id: View; icon: React.ReactNode; label: string }[] = [
    { id: 'chat',     icon: <MessageCircle size={20} />, label: 'Chat'     },
    { id: 'review',   icon: <Inbox size={20} />,         label: 'Review'   },
    { id: 'settings', icon: <Settings size={20} />,      label: 'Settings' },
  ]
  return (
    <nav className="md:hidden shrink-0 bg-paper-50/95 backdrop-blur-md border-t border-paper-200 flex pb-safe">
      {tabs.map(({ id, icon, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`flex-1 flex flex-col items-center justify-center gap-0.5 pt-1.5 pb-1 text-[10px] font-medium transition min-h-[52px] active:scale-95 touch-manipulation ${
            view === id ? 'text-accent-400' : 'text-paper-400'
          }`}
        >
          <span className={`relative transition ${view === id ? 'text-accent-400 drop-shadow-void' : 'text-paper-400'}`}>
            {icon}
            {id === 'review' && reviewCount > 0 && (
              <span className="absolute -top-1 -right-2 min-w-[14px] h-[14px] px-0.5 rounded-full bg-void-static text-[#1a100c] text-[9px] leading-[14px]">
                {reviewCount}
              </span>
            )}
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
  const [reviewCount, setReviewCount] = useState(0)

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

  useEffect(() => {
    let cancelled = false
    async function loadCount() {
      try {
        const rows = await listWikiPending()
        if (!cancelled) setReviewCount(rows.length)
      } catch {
        if (!cancelled) setReviewCount(0)
      }
    }
    void loadCount()
    const timer = window.setInterval(() => { void loadCount() }, 15000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [view])

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

  const lastCalendarId = [...messages].reverse().find((m) => m.role === 'assistant' && m.pendingCalendar)?.id

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
    <div className="h-[100dvh] min-h-0 flex overflow-hidden bg-transparent relative">
      {/* Desktop sidebar */}
      <Sidebar
        activeView={view}
        onViewChange={setView}
        sessions={sessions}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        reviewCount={reviewCount}
      />

      {/* Main column */}
      <div className="flex-1 min-h-0 flex flex-col min-w-0 overflow-hidden">

        <MobileHeader
          view={view}
          showHistory={showMobileHistory}
          unsortedCount={messages.filter((m) => m.role === 'assistant' && /Unsorted/.test(m.content)).length}
          onToggleHistory={() => setShowMobileHistory((v) => !v)}
          onOpenSettings={() => setView('settings')}
          onOpenUnsorted={() => setView('review')}
          onLogoClick={handleNewChat}
        />

        {/* View content */}
        {view === 'chat' ? (
          <>
            {showMobileHistory && (
              <div className="md:hidden shrink-0 border-b border-paper-200 bg-paper-50/95 px-3 py-3 backdrop-blur-sm">
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
              <div className="max-w-[720px] mx-auto px-3 md:px-5 py-3 md:py-4 pb-6">
                {loading ? (
                  <p className="text-sm text-paper-400 text-center py-8">Loading your chats…</p>
                ) : (
                  <>
                {reviewCount > 0 && (
                  <button
                    type="button"
                    onClick={() => setView('review')}
                    className="w-full mb-4 text-left bg-paper-100 border border-paper-300 rounded-2xl p-3.5"
                  >
                    <p className="text-xs font-semibold text-gold-300">
                      {reviewCount} note{reviewCount === 1 ? '' : 's'} waiting in Review
                    </p>
                    <p className="text-[11px] text-paper-700 mt-0.5">
                      Approve to file into the wiki. Nothing is added until you say yes.
                    </p>
                  </button>
                )}
                {showBanner && (
                  <BriefBanner
                    content={briefContent}
                    onDismiss={() => setBriefDismissed(true)}
                  />
                )}
                {messages.length === 0 ? (
                  <EmptyState />
                ) : (
                  <div className="space-y-1 pb-2">
                    {messages.map((m) => (
                      <MessageBubble
                        key={m.id}
                        message={m}
                        showCalendarActions={m.id === lastCalendarId && !sending}
                        onCalendarConfirm={() => handleSend('yes')}
                        onCalendarCancel={() => handleSend('no')}
                      />
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
        ) : view === 'review' ? (
          <div className="flex-1 overflow-hidden">
            <ReviewInbox />
          </div>
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
        <BottomNav view={view} onChange={setView} reviewCount={reviewCount} />
      </div>
    </div>
  )
}

export default App
