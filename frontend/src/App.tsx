import { useEffect, useRef, useState } from 'react'
import { Sidebar } from '@/components/Sidebar'
import { MessageBubble } from '@/components/MessageBubble'
import { ChatInput } from '@/components/ChatInput'
import { ReadingList } from '@/components/ReadingList'
import { useChat } from '@/hooks/useChat'
import { getMorningBriefLatest } from '@/lib/api'
import { X, Newspaper } from 'lucide-react'

type View = 'chat' | 'reading'

function BriefBanner({
  content,
  onDismiss,
}: {
  content: string
  onDismiss: () => void
}) {
  // Show just the first few lines as a preview
  const preview = content.split('\n').slice(0, 6).join('\n')
  return (
    <div className="bg-ink-800 border border-blue-700 rounded-xl p-4 mb-4 relative">
      <button
        onClick={onDismiss}
        className="absolute top-3 right-3 text-ink-400 hover:text-ink-200"
      >
        <X size={16} />
      </button>
      <div className="flex items-center gap-2 mb-2 pr-6">
        <Newspaper size={16} className="text-blue-400 shrink-0" />
        <span className="text-sm font-medium text-blue-300">Ross's Morning Brief</span>
      </div>
      <pre className="text-xs text-ink-300 whitespace-pre-wrap font-sans leading-relaxed line-clamp-5">
        {preview}
      </pre>
    </div>
  )
}

function App() {
  const [view, setView] = useState<View>('chat')
  const { messages, sending, send } = useChat()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [briefContent, setBriefContent] = useState<string | null>(null)
  const [briefDismissed, setBriefDismissed] = useState(false)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    getMorningBriefLatest()
      .then((data) => {
        if (data.content) setBriefContent(data.content)
      })
      .catch(() => {})
  }, [])

  const showBanner = briefContent && !briefDismissed && view === 'chat'

  return (
    <div className="h-screen flex">
      <Sidebar activeView={view} onViewChange={setView} />

      <main className="flex-1 flex flex-col min-w-0 pl-0 md:pl-0">
        {view === 'chat' ? (
          <>
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 md:px-6 py-4 pt-14 md:pt-4">
              {showBanner && (
                <div className="max-w-3xl mx-auto">
                  <BriefBanner
                    content={briefContent}
                    onDismiss={() => setBriefDismissed(true)}
                  />
                </div>
              )}
              {messages.length === 0 ? (
                <EmptyState />
              ) : (
                <div className="max-w-3xl mx-auto">
                  {messages.map((m) => (
                    <MessageBubble key={m.id} message={m} />
                  ))}
                </div>
              )}
            </div>
            <div className="max-w-3xl mx-auto w-full px-3 md:px-0">
              <ChatInput onSend={send} disabled={sending} />
            </div>
          </>
        ) : (
          <div className="flex flex-col flex-1 overflow-hidden pt-14 md:pt-0">
            <ReadingList />
          </div>
        )}
      </main>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center max-w-md px-4">
        <div className="text-4xl mb-3">🪄</div>
        <h2 className="text-xl font-semibold text-ink-100 mb-2">Hey, I'm Ross</h2>
        <p className="text-ink-400 mb-6">
          Your knowledge curator. Save articles, track what you're reading, and get a fresh AI digest
          every morning.
        </p>
        <div className="text-left bg-ink-800 rounded-lg p-4 text-sm text-ink-300 space-y-2">
          <p className="text-ink-100 font-medium">Try:</p>
          <p>· "save in notes https://arxiv.org/abs/…"</p>
          <p>· "show my reading list"</p>
          <p>· "what's new in AI?"</p>
          <p>· "mark Mamba as read"</p>
          <p>· "I had eggs for breakfast" (routes to Health)</p>
        </div>
      </div>
    </div>
  )
}

export default App
