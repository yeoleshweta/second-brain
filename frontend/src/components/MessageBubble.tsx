import ReactMarkdown from 'react-markdown'
import { Book, Heart, DollarSign, Calendar, Sparkles, FileText } from 'lucide-react'
import type { Message, Intent } from '@/types'

const intentMeta: Record<Intent, { icon: typeof Book; label: string; color: string }> = {
  knowledge: { icon: Book, label: 'Knowledge', color: 'text-purple-400' },
  health: { icon: Heart, label: 'Health', color: 'text-rose-400' },
  finance: { icon: DollarSign, label: 'Finance', color: 'text-emerald-400' },
  calendar: { icon: Calendar, label: 'Calendar', color: 'text-amber-400' },
  general: { icon: Sparkles, label: 'General', color: 'text-ink-300' },
}

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const intent = message.intent ? intentMeta[message.intent] : null
  const Icon = intent?.icon

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} my-3`}>
      <div
        className={`max-w-2xl rounded-2xl px-4 py-3 ${
          isUser ? 'bg-blue-600 text-white' : 'bg-ink-800 text-ink-100'
        }`}
      >
        {!isUser && intent && Icon && (
          <div className={`flex items-center gap-1.5 text-xs mb-2 ${intent.color}`}>
            <Icon size={14} />
            <span>{intent.label} Agent</span>
          </div>
        )}

        {message.status === 'thinking' ? (
          <div className="flex gap-1.5 py-1">
            <Dot delay="0ms" />
            <Dot delay="150ms" />
            <Dot delay="300ms" />
          </div>
        ) : (
          <div className="prose-chat">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {message.attachments && message.attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {message.attachments.map((a) => (
              <div
                key={a.fileId}
                className="flex items-center gap-1.5 bg-ink-700 rounded-md px-2 py-1 text-xs"
              >
                <FileText size={12} />
                {a.name}
              </div>
            ))}
          </div>
        )}

        {message.obsidianPath && (
          <div className="mt-2 text-xs text-ink-400 flex items-center gap-1.5">
            <FileText size={12} />
            <span>Saved to <code className="bg-ink-700 px-1 rounded">{message.obsidianPath}</code></span>
          </div>
        )}
      </div>
    </div>
  )
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="inline-block w-2 h-2 rounded-full bg-ink-400 animate-bounce"
      style={{ animationDelay: delay }}
    />
  )
}
