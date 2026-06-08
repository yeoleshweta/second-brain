/**
 * Friends TV show UI theme — design tokens + Behance caricature references.
 *
 * Visual inspiration (caricature / character art):
 * - Full cast: https://www.behance.net/gallery/104319041/Caricatures
 * - Monica:    https://www.behance.net/gallery/126728093/Monica-Geller
 * - Phoebe:    https://www.behance.net/gallery/126728127/Phoebe-Buffay
 *
 * Drop exported PNG/GIF assets into `public/friends/` to replace emoji avatars.
 *
 * iOS homescreen / Widgetsmith layout inspiration:
 * - https://www.pinterest.com/pin/42995371440140227/
 */

export const BEHANCE_REFERENCES = {
  fullCast: 'https://www.behance.net/gallery/104319041/Caricatures',
  monica: 'https://www.behance.net/gallery/126728093/Monica-Geller',
  phoebe: 'https://www.behance.net/gallery/126728127/Phoebe-Buffay',
} as const

export const PINTEREST_REFERENCES = {
  /** Friends app icons + Widgetsmith homescreen layout */
  homescreenIcons: 'https://www.pinterest.com/pin/42995371440140227/',
} as const

/** Classic logo dot colors (red / yellow / blue repeat) */
export const FRIENDS_LOGO_DOTS = ['#E63946', '#F4D03F', '#457B9D'] as const

/** Central Perk + Monica's apartment palette */
export const FRIENDS_COLORS = {
  purple: '#6B3FA0',
  purpleDark: '#4A2870',
  purpleLight: '#9B6BC4',
  frame: '#F4D03F',
  frameDark: '#D4AF37',
  sofa: '#E8751A',
  sofaDark: '#C85018',
  perkBrown: '#4A3728',
  cream: '#FAF0E4',
  awning: '#3D6B4F',
  brick: '#8B4513',
} as const

export interface CharacterTheme {
  id: string
  name: string
  /** Primary caricature emoji (Behance-style expressive stand-in) */
  emoji: string
  /** Secondary mood / prop emoji */
  mood: string
  /** Tailwind bg class for avatar circle */
  avatarBg: string
  /** Accent for badges and borders */
  accent: string
  catchphrase: string
  /** Optional local asset path under public/ */
  avatarAsset?: string
}

export const FRIENDS_CHARACTERS: Record<string, CharacterTheme> = {
  ross: {
    id: 'ross',
    name: 'Ross',
    emoji: '🦕',
    mood: '🦴',
    avatarBg: 'bg-gradient-to-br from-friends-sofa to-friends-sofa-dark',
    accent: 'text-friends-sofa',
    catchphrase: 'We were on a break!',
    avatarAsset: '/friends/ross.png',
  },
  monica: {
    id: 'monica',
    name: 'Monica',
    emoji: '👩‍🍳',
    mood: '🧼',
    avatarBg: 'bg-gradient-to-br from-friends-purple to-friends-purple-dark',
    accent: 'text-friends-purple',
    catchphrase: 'I know!',
    avatarAsset: '/friends/monica.png',
  },
  phoebe: {
    id: 'phoebe',
    name: 'Phoebe',
    emoji: '🎸',
    mood: '🐱',
    avatarBg: 'bg-gradient-to-br from-friends-awning to-emerald-700',
    accent: 'text-friends-awning',
    catchphrase: 'Smelly cat, smelly cat…',
    avatarAsset: '/friends/phoebe.png',
  },
  joey: {
    id: 'joey',
    name: 'Joey',
    emoji: '🍕',
    mood: '🤙',
    avatarBg: 'bg-gradient-to-br from-gold-400 to-amber-500',
    accent: 'text-gold-600',
    catchphrase: 'How you doin\'?',
    avatarAsset: '/friends/joey.png',
  },
  chandler: {
    id: 'chandler',
    name: 'Chandler',
    emoji: '🦆',
    mood: '☕',
    avatarBg: 'bg-gradient-to-br from-perk-400 to-perk-600',
    accent: 'text-perk-600',
    catchphrase: 'Could I BE any more sarcastic?',
    avatarAsset: '/friends/chandler.png',
  },
  rachel: {
    id: 'rachel',
    name: 'Rachel',
    emoji: '👗',
    mood: '💄',
    avatarBg: 'bg-gradient-to-br from-rose-400 to-rose-500',
    accent: 'text-rose-500',
    catchphrase: 'Oh… my… God!',
    avatarAsset: '/friends/rachel.png',
  },
}

/** Map agent id → Friends character theme */
export const AGENT_CHARACTER_MAP: Record<string, keyof typeof FRIENDS_CHARACTERS> = {
  knowledge: 'ross',
  health: 'monica',
  wellness: 'phoebe',
  lifestyle: 'joey',
  calendar: 'chandler',
  finance: 'chandler',
  style: 'rachel',
}

export const APP_BRAND = {
  slug: 'centralperk',
  displayName: 'Central Perk',
  tagline: 'The one where you learn everything',
} as const

export const CENTRAL_PERK = {
  name: APP_BRAND.displayName,
  slug: APP_BRAND.slug,
  tagline: APP_BRAND.tagline,
  coffeeEmoji: '☕',
} as const
