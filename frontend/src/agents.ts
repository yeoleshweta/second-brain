import type { Intent } from '@/types'
import { FRIENDS_CHARACTERS } from '@/theme/friends'

export interface AgentDef {
  id: string
  intent?: Intent
  name: string
  emoji: string
  moodEmoji: string
  specialty: string
  tagline: string
  catchphrase: string
  description: string
  phase: number
  live: boolean
  avatarBg: string
  badgeBg: string
  badgeFg: string
  borderColor: string
  suggestions: { label: string; prompt: string }[]
}

export const AGENTS: AgentDef[] = [
  {
    id: 'knowledge',
    intent: 'knowledge',
    name: 'Ross',
    emoji: FRIENDS_CHARACTERS.ross.emoji,
    moodEmoji: FRIENDS_CHARACTERS.ross.mood,
    specialty: 'Knowledge & Research',
    tagline: 'Your personal librarian',
    catchphrase: FRIENDS_CHARACTERS.ross.catchphrase,
    description:
      'Saves articles & papers, builds your daily digest, manages your reading list. Paleontology nerd energy — ask him anything.',
    phase: 1,
    live: true,
    avatarBg: 'bg-gradient-to-br from-friends-sofa to-friends-sofa-dark',
    badgeBg: 'bg-accent-50',
    badgeFg: 'text-friends-sofa-dark',
    borderColor: 'border-friends-frame',
    suggestions: [
      { label: 'Suggest reading', prompt: 'suggest me a few things to read today' },
      { label: 'Apple Books', prompt: 'what am I reading in Apple Books?' },
      { label: 'Save a link', prompt: 'save this article — paste any URL after this' },
      { label: 'My reading list', prompt: 'show my reading list' },
      { label: "What's new in AI?", prompt: "what's new in AI this week?" },
    ],
  },
  {
    id: 'calendar',
    intent: 'calendar',
    name: 'Chandler',
    emoji: FRIENDS_CHARACTERS.chandler.emoji,
    moodEmoji: FRIENDS_CHARACTERS.chandler.mood,
    specialty: 'Calendar & Networking',
    tagline: 'Could I BE any more organized?',
    catchphrase: FRIENDS_CHARACTERS.chandler.catchphrase,
    description:
      'Schedules meetings, shows your agenda, and keeps person notes in sync with Google Calendar.',
    phase: 2,
    live: true,
    avatarBg: 'bg-gradient-to-br from-perk-400 to-perk-600',
    badgeBg: 'bg-perk-100',
    badgeFg: 'text-perk-600',
    borderColor: 'border-perk-200',
    suggestions: [
      { label: "Today's agenda", prompt: "what's on today?" },
      { label: 'Schedule a meeting', prompt: 'schedule coffee with Sarah Tuesday at 3pm' },
      { label: 'Look up a contact', prompt: 'what do I know about Sarah?' },
      { label: 'This week', prompt: "what's on this week?" },
    ],
  },
  {
    id: 'finance',
    intent: 'finance',
    name: 'Finance',
    emoji: FRIENDS_CHARACTERS.chandler.emoji,
    moodEmoji: FRIENDS_CHARACTERS.chandler.mood,
    specialty: 'Finance & Money',
    tagline: 'Read-only money tracking',
    catchphrase: 'Could I BE any more helpful with money?',
    description: 'Tracks spending, surfaces subscriptions, writes your weekly financial review. Read-only — he never moves money.',
    phase: 5,
    live: false,
    avatarBg: 'bg-perk-500',
    badgeBg: 'bg-perk-100',
    badgeFg: 'text-perk-600',
    borderColor: 'border-perk-200',
    suggestions: [
      { label: "This month's spending", prompt: 'how much did I spend this month?' },
      { label: 'Find subscriptions', prompt: 'show me my recurring subscriptions' },
      { label: 'Weekly review', prompt: 'give me my weekly finance summary' },
    ],
  },
  {
    id: 'wellness',
    intent: 'general',
    name: 'Phoebe',
    emoji: FRIENDS_CHARACTERS.phoebe.emoji,
    moodEmoji: FRIENDS_CHARACTERS.phoebe.mood,
    specialty: 'Wellness & Ideas',
    tagline: 'Good vibes only',
    catchphrase: FRIENDS_CHARACTERS.phoebe.catchphrase,
    description: 'Meditation prompts, healing routines, and wonderfully weird life inspiration.',
    phase: 3,
    live: false,
    avatarBg: 'bg-friends-awning',
    badgeBg: 'bg-sage-100',
    badgeFg: 'text-friends-awning',
    borderColor: 'border-sage-400',
    suggestions: [
      { label: 'Morning meditation', prompt: 'give me a 5-minute morning meditation prompt' },
      { label: 'Inspire me', prompt: 'suggest something new I should try this week' },
      { label: 'Journaling prompt', prompt: 'give me a journaling prompt for today' },
    ],
  },
  {
    id: 'lifestyle',
    intent: undefined,
    name: 'Joey',
    emoji: FRIENDS_CHARACTERS.joey.emoji,
    moodEmoji: FRIENDS_CHARACTERS.joey.mood,
    specialty: 'Fun & Lifestyle',
    tagline: 'How you doin\'?',
    catchphrase: FRIENDS_CHARACTERS.joey.catchphrase,
    description: "Food, weekend plans, trending hobbies — Joey's got the fun stuff covered.",
    phase: 6,
    live: false,
    avatarBg: 'bg-gold-400',
    badgeBg: 'bg-gold-100',
    badgeFg: 'text-gold-600',
    borderColor: 'border-gold-300',
    suggestions: [
      { label: "What's trending?", prompt: "what's trending on the internet this week?" },
      { label: 'New hobby idea', prompt: 'suggest a new hobby I should try' },
      { label: 'Weekend plans', prompt: 'give me 3 fun things to do this weekend' },
    ],
  },
  {
    id: 'style',
    intent: undefined,
    name: 'Rachel',
    emoji: FRIENDS_CHARACTERS.rachel.emoji,
    moodEmoji: FRIENDS_CHARACTERS.rachel.mood,
    specialty: 'Fashion & Style',
    tagline: 'Oh… my… God!',
    catchphrase: FRIENDS_CHARACTERS.rachel.catchphrase,
    description: 'Fashion trends, outfits, hair and makeup — always on-trend.',
    phase: 7,
    live: false,
    avatarBg: 'bg-rose-400',
    badgeBg: 'bg-rose-100',
    badgeFg: 'text-rose-500',
    borderColor: 'border-rose-200',
    suggestions: [
      { label: 'Style my look', prompt: 'suggest an outfit for a casual Friday' },
      { label: 'Fashion this season', prompt: "what's trending in fashion this season?" },
      { label: 'Makeup inspo', prompt: 'give me a makeup look inspiration for a date night' },
    ],
  },
  {
    id: 'health',
    intent: 'health',
    name: 'Monica',
    emoji: FRIENDS_CHARACTERS.monica.emoji,
    moodEmoji: FRIENDS_CHARACTERS.monica.mood,
    specialty: 'Nutrition & Fitness',
    tagline: 'I know!',
    catchphrase: FRIENDS_CHARACTERS.monica.catchphrase,
    description: 'Logs meals, plans workouts, reads Apple Health data — competitively supportive.',
    phase: 2,
    live: true,
    avatarBg: 'bg-friends-purple',
    badgeBg: 'bg-paper-100',
    badgeFg: 'text-friends-purple-dark',
    borderColor: 'border-friends-purple-light',
    suggestions: [
      { label: 'Log a meal', prompt: 'I had oatmeal with berries for breakfast' },
      { label: 'Log a workout', prompt: 'I did 30 min yoga this morning' },
      { label: 'Weekly health check', prompt: 'how am I doing with my nutrition this week?' },
    ],
  },
]

export const AGENT_BY_INTENT: Partial<Record<Intent, AgentDef>> = {
  knowledge: AGENTS.find((a) => a.id === 'knowledge')!,
  calendar: AGENTS.find((a) => a.id === 'calendar')!,
  finance: AGENTS.find((a) => a.id === 'finance')!,
  health: AGENTS.find((a) => a.id === 'health')!,
  general: AGENTS.find((a) => a.id === 'wellness')!,
}
