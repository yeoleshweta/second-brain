import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import { AGENT_BY_INTENT } from '@/agents'
import { CharacterAvatarByAgentId } from '@/components/friends/CharacterAvatar'
import { SuggestionPicker } from '@/components/SuggestionPicker'
import { BookPicker } from '@/components/BookPicker'
import { openExternalUrl, isExternalUrl } from '@/lib/openExternal'
import type { Message } from '@/types'

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
  return (
    <div className="flex items-center gap-1.5 px-1 py-0.5" aria-label="Thinking…">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-paper-400"
          style={{ animation: `dotBounce 1.2s ease-in-out ${i * 0.18}s infinite` }}
        />
      ))}
    </div>
  )
}

// ── Obsidian save badge ───────────────────────────────────────────────────────
function ObsidianBadge({ path }: { path: string }) {
  const short = path.replace(/^.*\/SecondBrain\//, '').replace(/^.*\/Documents\//, '')
  return (
    <div className="flex items-center gap-1.5 mt-2 py-1.5 px-2.5 bg-sage-100 rounded-lg w-fit max-w-full">
      <span className="text-xs shrink-0">🪄</span>
      <span className="text-[10px] font-mono text-sage-500 leading-none truncate">{short}</span>
    </div>
  )
}

// ── User message ──────────────────────────────────────────────────────────────
function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end py-1">
      <div className="max-w-[85%] md:max-w-[65%]">
        <div className="bg-friends-purple text-white rounded-[22px] rounded-br-[6px] px-4 py-2.5 shadow-card border border-friends-purple-dark/30">
          <p className="text-sm leading-relaxed break-words">{content}</p>
        </div>
      </div>
    </div>
  )
}

// ── Assistant message ─────────────────────────────────────────────────────────
function AssistantBubble({ message }: { message: Message }) {
  const { content, status, intent, obsidianPath, digestItems, suggestItems, bookItems } = message
  const agent = intent ? AGENT_BY_INTENT[intent] : null
  const isThinking = status === 'thinking' && !content
  const isError = status === 'error'

  const agentDef = intent ? AGENT_BY_INTENT[intent] : null
  const agentId = agentDef?.id ?? 'knowledge'

  return (
    <div className="flex items-end gap-2.5 py-1">
      {agentDef ? (
        <CharacterAvatarByAgentId agentId={agentId} size="md" framed />
      ) : (
        <div className="w-9 h-9 rounded-xl bg-paper-200 flex items-center justify-center text-lg shrink-0 self-end mb-0.5 shadow-card">
          🤖
        </div>
      )}

      <div className="flex-1 min-w-0">
        {agent && (
          <div className="flex items-center gap-1.5 mb-1.5 ml-0.5">
            <span className="text-xs font-bold text-paper-600">{agent.name}</span>
            <span
              className={`hidden sm:inline text-[10px] font-semibold px-2 py-0.5 rounded-full ${agent.badgeBg} ${agent.badgeFg}`}
            >
              {agent.specialty}
            </span>
          </div>
        )}

        <div
          className={`max-w-[85%] md:max-w-[65%] bg-white rounded-[22px] rounded-bl-[6px] px-4 py-3 shadow-card border-2 ${
            agent ? agent.borderColor : 'border-paper-100'
          } ${isError ? 'bg-rust-100 border-rust-400/30' : ''}`}
        >
          {isThinking ? (
            <ThinkingDots />
          ) : (
            <div className="prose-chat text-sm leading-relaxed break-words">
              <ReactMarkdown components={markdownLinkComponents}>{content}</ReactMarkdown>
            </div>
          )}

          {obsidianPath && <ObsidianBadge path={obsidianPath} />}
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
                className="flex items-start gap-2.5 bg-white border border-paper-100 rounded-xl px-3 py-3 shadow-card active:bg-paper-50 transition group min-h-[48px] touch-manipulation cursor-pointer w-full min-w-0"
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
export function MessageBubble({ message }: { message: Message }) {
  return message.role === 'user' ? (
    <UserBubble content={message.content} />
  ) : (
    <AssistantBubble message={message} />
  )
}
