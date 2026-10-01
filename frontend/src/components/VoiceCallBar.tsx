import { PhoneOff } from 'lucide-react'
import type { VoicePhase } from '@/lib/voice'

interface Props {
  phase: VoicePhase
  level: number
  error: string | null
  onHangup: () => void
  onTap: () => void
}

function labelFor(phase: VoicePhase): string {
  switch (phase) {
    case 'connecting':
      return 'Connecting mic…'
    case 'listening':
      return 'Listening — pause when you are done, or tap to send'
    case 'transcribing':
      return 'Transcribing…'
    case 'waiting':
      return 'Thinking…'
    case 'speaking':
      return 'Speaking — tap to interrupt'
    case 'blocked':
      return 'Live mic is blocked on this page'
    default:
      return 'Talk'
  }
}

export function VoiceCallBar({ phase, level, error, onHangup, onTap }: Props) {
  const hot = phase === 'listening' && level > 0.12
  return (
    <div className="mb-2 rounded-2xl border-2 border-friends-purple/40 bg-white px-3 py-2.5 shadow-card">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onTap}
          className="flex-1 min-w-0 flex items-center gap-3 text-left touch-manipulation"
          aria-label={labelFor(phase)}
        >
          <div
            className={`flex items-end gap-0.5 h-7 shrink-0 ${
              phase === 'listening' ? 'opacity-100' : 'opacity-40'
            }`}
          >
            <span className={`w-1 rounded-full bg-friends-purple ${hot ? 'h-4' : 'h-2'}`} />
            <span className={`w-1 rounded-full bg-friends-purple ${hot ? 'h-6' : 'h-3'}`} />
            <span className={`w-1 rounded-full bg-friends-purple ${hot ? 'h-7 animate-pulse' : 'h-4'}`} />
            <span className={`w-1 rounded-full bg-friends-purple ${hot ? 'h-6' : 'h-3'}`} />
            <span className={`w-1 rounded-full bg-friends-purple ${hot ? 'h-4' : 'h-2'}`} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-paper-800 truncate">{labelFor(phase)}</p>
            {error ? (
              <p className="text-[11px] text-paper-500 leading-snug">{error}</p>
            ) : (
              <p className="text-[11px] text-paper-400">Same OpenAI key as chat — Whisper in, speech out</p>
            )}
          </div>
        </button>
        <button
          type="button"
          onClick={onHangup}
          className="touch-target shrink-0 flex items-center justify-center rounded-xl bg-rust-400 text-white active:scale-95"
          aria-label="Hang up"
        >
          <PhoneOff size={18} />
        </button>
      </div>
    </div>
  )
}
