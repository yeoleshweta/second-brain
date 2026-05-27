import { useEffect, useRef } from 'react'
import { Sidebar } from '@/components/Sidebar'
import { MessageBubble } from '@/components/MessageBubble'
import { ChatInput } from '@/components/ChatInput'
import { useChat } from '@/hooks/useChat'

function App() {
  const { messages, sending, send } = useChat()
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages])

  return (
    <div className="h-screen flex">
      <Sidebar />

      <main className="flex-1 flex flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4">
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

        <div className="max-w-3xl mx-auto w-full">
          <ChatInput onSend={send} disabled={sending} />
        </div>
      </main>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center max-w-md">
        <div className="text-4xl mb-3">🧠</div>
        <h2 className="text-xl font-semibold text-ink-100 mb-2">Your second brain</h2>
        <p className="text-ink-400 mb-6">
          Tell me anything — what you ate, what you read, who you met, what you bought. I'll route
          it to the right agent and save it to your Obsidian vault.
        </p>
        <div className="text-left bg-ink-800 rounded-lg p-4 text-sm text-ink-300 space-y-2">
          <p className="text-ink-100 font-medium">Try:</p>
          <p>· "I just ate two eggs and avocado toast"</p>
          <p>· "Save this paper: https://arxiv.org/abs/..."</p>
          <p>· "Coffee with Sarah next Tuesday at 3pm"</p>
          <p>· "What did I spend on coffee this month?"</p>
        </div>
      </div>
    </div>
  )
}

export default App
