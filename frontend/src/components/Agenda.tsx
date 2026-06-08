import { useCallback, useEffect, useState } from 'react'
import { Calendar, RefreshCw, Users } from 'lucide-react'
import { fetchChandlerAgenda, type AgendaEvent } from '@/lib/api'
import { CharacterAvatarByAgentId } from '@/components/friends/CharacterAvatar'

type Scope = 'today' | 'week'

const SCOPES: { id: Scope; label: string }[] = [
  { id: 'today', label: 'Today' },
  { id: 'week', label: 'This week' },
]

function EventCard({ event }: { event: AgendaEvent }) {
  return (
    <div className="bg-white rounded-2xl border border-paper-100 shadow-card p-4 flex gap-3">
      <div className="w-14 shrink-0 flex flex-col items-center justify-center rounded-xl bg-perk-50 border border-perk-100 py-2">
        <span className="text-xs font-bold text-perk-600 uppercase tracking-wide">
          {event.time_label.replace(/[0-9:]/g, '').trim() || '—'}
        </span>
        <span className="text-sm font-bold text-perk-700 leading-tight">
          {event.time_label.replace(/[^0-9:]/g, '') || event.time_label}
        </span>
      </div>

      <div className="flex-1 min-w-0 space-y-1.5">
        <p className="font-semibold text-sm text-paper-800 leading-snug">{event.summary}</p>
        {event.attendees.length > 0 && (
          <div className="flex items-start gap-1.5 text-xs text-paper-500">
            <Users size={12} className="shrink-0 mt-0.5 text-paper-400" />
            <span className="line-clamp-2">{event.attendees.join(', ')}</span>
          </div>
        )}
        {event.prep_note && (
          <p className="text-xs text-friends-purple italic leading-snug bg-friends-cream/80 rounded-lg px-2.5 py-1.5 border border-friends-frame/40">
            Prep: {event.prep_note}
          </p>
        )}
      </div>
    </div>
  )
}

export function Agenda() {
  const [scope, setScope] = useState<Scope>('today')
  const [events, setEvents] = useState<AgendaEvent[]>([])
  const [reply, setReply] = useState('')
  const [connected, setConnected] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (nextScope: Scope) => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchChandlerAgenda(nextScope)
      setEvents(data.events ?? [])
      setReply(data.reply ?? '')
      setConnected(data.connected !== false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load agenda')
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(scope)
  }, [scope, load])

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="shrink-0 px-4 md:px-6 pt-4 pb-3 border-b border-paper-200 bg-white/80 backdrop-blur-sm">
        <div className="max-w-2xl mx-auto flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <CharacterAvatarByAgentId agentId="calendar" size="md" framed />
            <div className="min-w-0">
              <h1 className="text-lg font-bold text-paper-800 flex items-center gap-2">
                <Calendar size={18} className="text-perk-500 shrink-0" />
                Chandler&apos;s Agenda
              </h1>
              <p className="text-xs text-paper-500 truncate">Google Calendar · person prep notes</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void load(scope)}
            disabled={loading}
            className="touch-target flex items-center justify-center rounded-xl bg-paper-100 active:bg-paper-200 text-paper-500 transition disabled:opacity-50"
            aria-label="Refresh agenda"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        <div className="max-w-2xl mx-auto mt-3 flex gap-2">
          {SCOPES.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setScope(id)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition ${
                scope === id
                  ? 'bg-perk-100 text-perk-700 border border-perk-200'
                  : 'bg-paper-50 text-paper-500 border border-paper-100 hover:bg-paper-100'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto mobile-scroll px-4 md:px-6 py-4">
        <div className="max-w-2xl mx-auto space-y-3">
          {loading && events.length === 0 && (
            <p className="text-sm text-paper-400 text-center py-12">Loading your calendar…</p>
          )}

          {error && (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              {error}
            </div>
          )}

          {!loading && !error && !connected && (
            <div className="rounded-2xl border border-gold-200 bg-gold-50 p-4 text-sm text-paper-700 leading-relaxed">
              {reply || 'Google Calendar is not connected yet. See docs/phase-2-iphone-setup.md for setup.'}
            </div>
          )}

          {!loading && !error && connected && events.length === 0 && (
            <div className="rounded-2xl border border-paper-100 bg-white p-6 text-center shadow-card">
              <p className="text-sm text-paper-600 leading-relaxed">
                {reply || 'Nothing scheduled. Ask Chandler in chat to add something.'}
              </p>
            </div>
          )}

          {events.map((event) => (
            <EventCard key={event.id || `${event.start}-${event.summary}`} event={event} />
          ))}
        </div>
      </div>
    </div>
  )
}
