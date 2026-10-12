import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import { SuggestionPicker } from '@/components/SuggestionPicker'
import { BookPicker } from '@/components/BookPicker'
import { splitCaptureStatus, type CaptureChip } from '@/lib/captureStatus'
import { openExternalUrl, isExternalUrl } from '@/lib/openExternal'
import { isPlainMode, speakReply } from '@/lib/voice'
import type { Message } from '@/types'
import { Volume2 } from 'lucide-react'

const markdownLinkComponents: Components = {
  a: ({ href, children }) => {
    if (!href) return <span>{children}</span>
    const external = isExternalUrl(href)
    if (external) {
      return (
        <button
          type="button"
          className="text-friends-purple underline underline-offset-2 decoration-friends-purple/40 hover:text-friends-purple-dark transition text-left"
          onClick={() => openExternalUrl(href)}
        >
          {children}
        </button>
      )
    }
    return (
      <a href={href} className="text-friends-purple underline underline-offset-2">
        {children}
      </a>
    )
  },
}

// ── Thinking dots ─────────────────────────────────────────────────────────────
function ThinkingDots() {
  if (!isPlainMode()) {
    return (
      <div className="void-wire" aria-label="The Void is typing">
        <span className="void-bulb bg-[#FF4545]" />
        <span className="void-bulb bg-[#F2B84B]" />
        <span className="void-bulb bg-[#5BA8E6]" />
        <span className="void-bulb bg-[#5FCB7A]" />
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1.5 px-1 py-0.5" aria-label="The Void is typing">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-void-muted"
          style={{ animation: `dotBounce 1.2s ease-in-out ${i * 0.18}s infinite` }}
        />
      ))}
    </div>
  )
}

function StatusChipView({ chip }: { chip: CaptureChip }) {
  const [open, setOpen] = useState(false)
  const tone =
    chip.kind === 'log'
      ? 'border-void-red text-void-text'
      : chip.kind === 'unsorted'
        ? 'border-void-upside text-void-text'
        : chip.kind === 'queued'
          ? 'border-void-static text-void-text'
          : 'border-void-muted text-void-muted'
  const mark =
    chip.kind === 'log' ? (
      <span className="w-2 h-2 rounded-full bg-void-red shrink-0" />
    ) : chip.kind === 'unsorted' ? (
      <span className="text-void-upside text-[10px] leading-none shrink-0" aria-hidden>▼</span>
    ) : chip.kind === 'queued' ? (
      <span className="w-2 h-2 rounded-full border border-void-static shrink-0" />
    ) : (
      <span className="w-2 h-2 rounded-full border border-void-muted shrink-0" />
    )
  const words =
    chip.kind === 'log'
      ? 'Saved · Log'
      : chip.kind === 'unsorted'
        ? 'Saved · Unsorted'
        : chip.kind === 'queued'
          ? 'Not saved yet · retrying'
          : 'Not saved'

  return (
    <div className="mt-2">
      <button
        type="button"
        className={`inline-flex items-center gap-1.5 min-h-[32px] rounded-full border px-2.5 py-1 text-[13px] font-medium ${tone}`}
        aria-label={chip.label}
        onClick={() => chip.path && setOpen((v) => !v)}
      >
        {mark}
        <span>{words}</span>
        {(chip.kind === 'log' || chip.kind === 'unsorted') && chip.typeLabel && (
          <span className="rounded-full bg-void-tag px-1.5 py-0.5 text-[12px] font-medium text-[#1a100c]">
            {chip.typeLabel}
          </span>
        )}
      </button>
      {open && chip.path && (
        <p className="mt-1 text-[12px] text-void-muted break-all">{chip.path}</p>
      )}
    </div>
  )
}

function clockLabel(iso?: string): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

// ── User message ──────────────────────────────────────────────────────────────
function UserBubble({ message }: { message: Message }) {
  const { content, attachments, createdAt } = message
  const time = clockLabel(createdAt)
  return (
    <div className="flex justify-end py-1">
      <div className="max-w-[85%] md:max-w-[65%]">
        <div className="bg-void-surface/70 backdrop-blur-md text-void-text rounded-2xl px-4 py-2.5 border border-white/10">
          {content ? (
            <p className="text-base leading-[1.45] break-words whitespace-pre-wrap">{content}</p>
          ) : (
            <p className="text-base italic text-void-muted">Attachment</p>
          )}
          {attachments && attachments.length > 0 && (
            <p className="text-[12px] text-void-muted mt-1 truncate">
              {attachments.map((a) => a.name).join(', ')}
            </p>
          )}
        </div>
        {time && <p className="mt-1 text-right text-[12px] text-void-muted">{time}</p>}
      </div>
    </div>
  )
}

// ── Assistant message ─────────────────────────────────────────────────────────
function AssistantBubble({
  message,
  showCalendarActions,
  onCalendarConfirm,
  onCalendarCancel,
}: {
  message: Message
  showCalendarActions?: boolean
  onCalendarConfirm?: () => void
  onCalendarCancel?: () => void
}) {
  const { content, status, intent, obsidianPath, pendingCalendar, digestItems, suggestItems, bookItems } = message
  const isThinking = status === 'thinking' && !content
  const isError = status === 'error'
  const parsed = !isThinking && !isError ? splitCaptureStatus(content) : null
  const body = parsed?.body || content
  const chip = parsed?.chip
  const plain = isPlainMode()

  return (
    <div className="flex items-start gap-2 py-1">
      <div className="flex-1 min-w-0">
        <div className={`max-w-[85%] md:max-w-[72%] border-l-2 pl-3 ${isError ? 'border-void-static' : 'border-void-red'}`}>
          {isThinking ? (
            <ThinkingDots />
          ) : (
            <>
              {body && (
                <div className="flex items-start gap-2">
                  <div className="prose-chat min-w-0 flex-1 text-base leading-[1.45] break-words text-void-text">
                    <ReactMarkdown components={markdownLinkComponents}>{body}</ReactMarkdown>
                  </div>
                  <button
                    type="button"
                    className="touch-target flex items-center justify-center text-void-muted"
                    aria-label="Play reply"
                    onClick={() => void speakReply(body, intent)}
                  >
                    <Volume2 size={14} />
                  </button>
                </div>
              )}
              {chip && !plain && (
                <p className="mt-2 text-[13px] italic text-void-muted">{chip.phrase}</p>
              )}
              {chip && <StatusChipView chip={{ ...chip, path: chip.path || obsidianPath }} />}
            </>
          )}

          {showCalendarActions && pendingCalendar && (
            <div className="mt-3 flex flex-col gap-2">
              <p className="text-[11px] text-paper-500">
                {pendingCalendar.summary} · {pendingCalendar.when}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={onCalendarConfirm}
                  className="min-h-[44px] px-3.5 text-sm font-medium text-white bg-sage-600 active:bg-sage-700 rounded-xl"
                >
                  {pendingCalendar.kind === 'reminder' ? 'Add reminder' : 'Add to calendar'}
                </button>
                <button
                  type="button"
                  onClick={onCalendarCancel}
                  className="min-h-[44px] px-3.5 text-sm font-medium text-paper-700 bg-paper-100 active:bg-paper-200 rounded-xl"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Full-width pickers — outside the narrow message bubble */}
        {digestItems && digestItems.length > 0 && !suggestItems?.length && !bookItems?.length && (
          <div className="mt-2 space-y-1.5 w-full min-w-0">
            {digestItems.slice(0, 5).map((item) => (
              <a
                key={item.url}
                href={item.url}
                onClick={(e) => {
                  e.preventDefault()
                  openExternalUrl(item.url)
                }}
                className="flex items-start gap-2.5 bg-paper-50 border border-paper-100 rounded-xl px-3 py-3 shadow-card active:bg-paper-50 transition group min-h-[48px] touch-manipulation cursor-pointer w-full min-w-0"
              >
                <div className="w-7 h-7 rounded-lg bg-paper-100 flex items-center justify-center text-sm shrink-0 mt-0.5">
                  {item.kind === 'paper' ? '📄' : '🔗'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-paper-800 group-hover:text-accent-500 leading-snug line-clamp-2">
                    {item.title}
                  </p>
                  {item.summary && (
                    <p className="text-[10px] text-paper-500 mt-1 line-clamp-2 leading-relaxed">
                      {item.summary}
                    </p>
                  )}
                  <p className="text-[10px] text-paper-400 mt-0.5 truncate">{item.source}</p>
                </div>
              </a>
            ))}
          </div>
        )}

        {suggestItems && suggestItems.length > 0 && (
          <SuggestionPicker items={suggestItems} />
        )}

        {bookItems && bookItems.length > 0 && (
          <div className="mt-2 w-full min-w-0">
            <BookPicker items={bookItems} />
          </div>
        )}
      </div>
    </div>
  )
}

// ── Public export ─────────────────────────────────────────────────────────────
export function MessageBubble({
  message,
  showCalendarActions,
  onCalendarConfirm,
  onCalendarCancel,
}: {
  message: Message
  showCalendarActions?: boolean
  onCalendarConfirm?: () => void
  onCalendarCancel?: () => void
}) {
  return message.role === 'user' ? (
    <UserBubble message={message} />
  ) : (
    <AssistantBubble
      message={message}
      showCalendarActions={showCalendarActions}
      onCalendarConfirm={onCalendarConfirm}
      onCalendarCancel={onCalendarCancel}
    />
  )
}
