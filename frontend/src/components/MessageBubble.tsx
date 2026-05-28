import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Book, Heart, DollarSign, Calendar, Sparkles, FileText, ExternalLink, BookmarkPlus, Check, Loader2 } from 'lucide-react'
import { saveItemDirect } from '@/lib/api'
import type { DigestItem, Message, Intent } from '@/types'

const intentMeta: Record<Intent, { icon: typeof Book; label: string; color: string }> = {
  knowledge: { icon: Book, label: 'Ross', color: 'text-purple-400' },
  health: { icon: Heart, label: 'Health', color: 'text-rose-400' },
  finance: { icon: DollarSign, label: 'Finance', color: 'text-emerald-400' },
  calendar: { icon: Calendar, label: 'Calendar', color: 'text-amber-400' },
  general: { icon: Sparkles, label: 'General', color: 'text-ink-300' },
}

// ── Digest item card ─────────────────────────────────────────────────────────

type SaveState = 'idle' | 'saving' | 'saved' | 'duplicate'

function DigestCard({ item }: { item: DigestItem }) {
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [expanded, setExpanded] = useState(false)

  const summary = item.summary?.trim()
  const shortSummary = summary && summary.length > 160 ? summary.slice(0, 160).trimEnd() + '…' : summary

  const handleSave = async () => {
    setSaveState('saving')
    try {
      const result = await saveItemDirect({
        url: item.url,
        title: item.title,
        summary: item.summary,
        source: item.source,
        kind: item.kind,
      })
      setSaveState(result.duplicate ? 'duplicate' : 'saved')
    } catch {
      setSaveState('idle')
    }
  }

  const saveLabel = {
    idle: 'Save',
    saving: 'Saving…',
    saved: 'Saved ✓',
    duplicate: 'Already saved',
  }[saveState]

  return (
    <div className="bg-ink-700 rounded-xl p-3 space-y-2 border border-ink-600">
      {/* Title + source row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-ink-100 hover:text-blue-400 flex items-start gap-1 leading-snug"
            >
              <span className="break-words">{item.title}</span>
              <ExternalLink size={11} className="shrink-0 mt-0.5 opacity-60" />
            </a>
          ) : (
            <span className="text-sm font-medium text-ink-100 leading-snug">{item.title}</span>
          )}
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            {item.source && (
              <span className="text-xs bg-ink-600 text-ink-300 px-1.5 py-0.5 rounded-full">
                {item.source}
              </span>
            )}
            {item.date && item.date !== 'n/a' && (
              <span className="text-xs text-ink-500">{item.date}</span>
            )}
          </div>
        </div>

        {/* Save button */}
        <button
          onClick={handleSave}
          disabled={saveState !== 'idle'}
          title={saveLabel}
          className={`shrink-0 flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg min-h-[32px] transition font-medium ${
            saveState === 'idle'
              ? 'bg-blue-600 hover:bg-blue-500 text-white'
              : saveState === 'saving'
              ? 'bg-ink-600 text-ink-400 cursor-not-allowed'
              : 'bg-emerald-800 text-emerald-300 cursor-default'
          }`}
        >
          {saveState === 'saving' ? (
            <Loader2 size={12} className="animate-spin" />
          ) : saveState === 'saved' || saveState === 'duplicate' ? (
            <Check size={12} />
          ) : (
            <BookmarkPlus size={12} />
          )}
          <span className="hidden sm:inline">{saveLabel}</span>
        </button>
      </div>

      {/* Summary */}
      {summary && (
        <div className="text-xs text-ink-300 leading-relaxed">
          {expanded || !shortSummary ? summary : shortSummary}
          {!expanded && shortSummary && shortSummary !== summary && (
            <button
              onClick={() => setExpanded(true)}
              className="ml-1 text-blue-400 hover:text-blue-300"
            >
              more
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main bubble ──────────────────────────────────────────────────────────────

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
            <span>{intent.label}</span>
          </div>
        )}

        {message.status === 'thinking' ? (
          <div className="flex gap-1.5 py-1">
            <Dot delay="0ms" />
            <Dot delay="150ms" />
            <Dot delay="300ms" />
          </div>
        ) : (
          <>
            <div className="prose-chat">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>

            {/* Digest cards */}
            {message.digestItems && message.digestItems.length > 0 && (
              <div className="mt-3 space-y-2">
                {message.digestItems.map((item, i) => (
                  <DigestCard key={item.url || i} item={item} />
                ))}
              </div>
            )}
          </>
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
            <span>
              Saved to{' '}
              <code className="bg-ink-700 px-1 rounded">{message.obsidianPath}</code>
            </span>
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
