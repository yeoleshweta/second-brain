import { readText, writeText } from './blob'

const STATE_PATH = 'state/app.json'

export type StoredMessage = {
  id: string
  role: string
  content: string
  intent?: string | null
  created_at: string
  obsidianPath?: string
}

export type StoredSession = {
  id: string
  title: string
  created_at: string
  updated_at: string
  messages: StoredMessage[]
}

export type AppState = {
  sessions: StoredSession[]
  settings: Record<string, string>
}

const DEFAULT_SETTINGS: Record<string, string> = {
  daily_reading_minutes_goal: '15',
  daily_practice_minutes_goal: '60',
  active_skills: 'guitar,system-design,coding',
  quiet_hours_start: '22:00',
  quiet_hours_end: '06:00',
  nudges_paused_until: '',
  nudge_morning_brief: 'true',
  nudge_mid_day_reading: 'true',
  nudge_evening_reading: 'true',
  nudge_evening_practice: 'true',
  nudge_weekly_review: 'true',
  nudge_discovery: 'true',
}

function emptyState(): AppState {
  return { sessions: [], settings: { ...DEFAULT_SETTINGS } }
}

export async function loadState(): Promise<AppState> {
  const raw = await readText(STATE_PATH)
  if (!raw) return emptyState()
  try {
    const parsed = JSON.parse(raw) as AppState
    return {
      sessions: Array.isArray(parsed.sessions) ? parsed.sessions : [],
      settings: { ...DEFAULT_SETTINGS, ...(parsed.settings || {}) },
    }
  } catch {
    return emptyState()
  }
}

export async function saveState(state: AppState): Promise<void> {
  await writeText(STATE_PATH, JSON.stringify(state), 'application/json')
}

export function sessionToApi(row: StoredSession) {
  return {
    id: row.id,
    title: row.title,
    created_at: row.created_at,
    updated_at: row.updated_at,
    message_count: row.messages.length,
  }
}

export function titleFromMessage(message: string): string {
  const t = (message || '').trim().replace(/\s+/g, ' ')
  if (!t) return 'New chat'
  return t.length > 48 ? `${t.slice(0, 45)}…` : t
}
