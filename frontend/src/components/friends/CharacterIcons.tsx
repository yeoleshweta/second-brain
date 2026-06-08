import type { FC, ReactNode } from 'react'

/** Widgetsmith-style SVG character marks — bold props, readable at squircle size */

interface IconProps {
  className?: string
}

function SvgWrap({ className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      {children}
    </svg>
  )
}

/** Ross — paleontologist T-Rex (the one with the dinosaurs) */
export function RossCharacterIcon({ className }: IconProps) {
  return (
    <SvgWrap className={className}>
      {/* Tail */}
      <path
        d="M44 38 C52 34 60 36 62 44 C60 50 52 48 46 42 Z"
        fill="#4A7A32"
      />
      {/* Body */}
      <ellipse cx="34" cy="40" rx="14" ry="13" fill="#5C9A3E" />
      <ellipse cx="34" cy="40" rx="10" ry="9" fill="#6BAF48" opacity="0.45" />
      {/* Head + snout */}
      <path
        d="M12 30 C8 26 10 18 18 16 C26 14 32 20 30 28 C28 34 20 36 14 32 Z"
        fill="#5C9A3E"
      />
      <path d="M12 30 C14 34 20 34 24 30" fill="#4A7A32" />
      {/* Eye */}
      <circle cx="22" cy="24" r="3.5" fill="#FAF0E4" />
      <circle cx="23" cy="24" r="1.8" fill="#2C1810" />
      <circle cx="24" cy="23" r="0.6" fill="#FAF0E4" />
      {/* Tiny arm — Ross energy */}
      <path d="M28 36 L24 30 L30 29 Z" fill="#4A7A32" />
      {/* Spine bumps */}
      <circle cx="38" cy="30" r="2" fill="#4A7A32" />
      <circle cx="42" cy="33" r="1.6" fill="#4A7A32" />
      <circle cx="46" cy="37" r="1.3" fill="#4A7A32" />
      {/* Fossil bone accent */}
      <path
        d="M48 48 C50 46 54 47 54 50 C54 53 50 54 48 52 C46 50 46 49 48 48 Z"
        fill="#FAF0E4"
        stroke="#D4AF37"
        strokeWidth="1"
      />
    </SvgWrap>
  )
}

/** Monica — competitive chef */
export function MonicaCharacterIcon({ className }: IconProps) {
  return (
    <SvgWrap className={className}>
      <circle cx="32" cy="38" r="14" fill="#FAF0E4" opacity="0.25" />
      {/* Chef toque */}
      <path
        d="M18 28 C18 18 26 14 32 14 C38 14 46 18 46 28 L44 32 L20 32 Z"
        fill="#FAF0E4"
        stroke="#E8DCC8"
        strokeWidth="1"
      />
      <ellipse cx="32" cy="28" rx="12" ry="5" fill="#F5F0E6" />
      {/* Face */}
      <circle cx="32" cy="40" r="11" fill="#F4C9A8" />
      {/* Eyes — intense */}
      <circle cx="28" cy="38" r="2" fill="#2C1810" />
      <circle cx="36" cy="38" r="2" fill="#2C1810" />
      {/* Sponge prop */}
      <rect x="44" y="44" width="10" height="12" rx="2" fill="#F4D03F" stroke="#D4AF37" strokeWidth="1" />
      <circle cx="47" cy="48" r="1" fill="#E8B923" opacity="0.6" />
      <circle cx="51" cy="51" r="1" fill="#E8B923" opacity="0.6" />
    </SvgWrap>
  )
}

/** Phoebe — guitar & Smelly Cat vibes */
export function PhoebeCharacterIcon({ className }: IconProps) {
  return (
    <SvgWrap className={className}>
      {/* Guitar body */}
      <ellipse cx="32" cy="42" rx="16" ry="14" fill="#8B5E3C" stroke="#5D4037" strokeWidth="1.5" />
      <circle cx="32" cy="42" r="5" fill="#3D2817" opacity="0.5" />
      {/* Neck */}
      <rect x="29" y="10" width="6" height="26" rx="2" fill="#6D4C41" />
      {/* Headstock */}
      <path d="M26 10 L38 10 L36 6 L28 6 Z" fill="#5D4037" />
      {/* Strings */}
      <line x1="30" y1="14" x2="30" y2="36" stroke="#D4AF37" strokeWidth="0.8" />
      <line x1="32" y1="14" x2="32" y2="36" stroke="#D4AF37" strokeWidth="0.8" />
      <line x1="34" y1="14" x2="34" y2="36" stroke="#D4AF37" strokeWidth="0.8" />
      {/* Cat silhouette */}
      <path
        d="M48 20 L50 16 L52 20 L52 26 C52 28 48 28 48 26 Z"
        fill="#FAF0E4"
        opacity="0.9"
      />
    </SvgWrap>
  )
}

/** Joey — pizza, always */
export function JoeyCharacterIcon({ className }: IconProps) {
  return (
    <SvgWrap className={className}>
      {/* Pizza slice */}
      <path
        d="M32 8 L54 52 L10 52 Z"
        fill="#F4A020"
        stroke="#C85018"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* Crust */}
      <path d="M18 46 L46 46 L32 14 Z" fill="#E8751A" opacity="0.35" />
      <path d="M14 48 Q32 44 50 48" stroke="#C85018" strokeWidth="3" fill="none" strokeLinecap="round" />
      {/* Pepperoni */}
      <circle cx="28" cy="36" r="4" fill="#C62828" />
      <circle cx="38" cy="42" r="3.5" fill="#C62828" />
      <circle cx="34" cy="28" r="3" fill="#C62828" />
      {/* Cheese drip */}
      <path d="M24 40 Q26 44 24 46" stroke="#FAF0E4" strokeWidth="2" strokeLinecap="round" />
    </SvgWrap>
  )
}

/** Chandler — rubber duck (Chick & Duck era) */
export function ChandlerCharacterIcon({ className }: IconProps) {
  return (
    <SvgWrap className={className}>
      {/* Duck body */}
      <ellipse cx="32" cy="40" rx="18" ry="14" fill="#F4D03F" stroke="#D4AF37" strokeWidth="1.5" />
      {/* Head */}
      <circle cx="22" cy="28" r="11" fill="#F4D03F" stroke="#D4AF37" strokeWidth="1.5" />
      {/* Beak */}
      <path d="M10 28 L16 26 L16 30 Z" fill="#E8751A" />
      {/* Eye — sarcastic half-lid */}
      <circle cx="20" cy="26" r="2.5" fill="#2C1810" />
      <path d="M17 24 Q20 22 23 24" stroke="#2C1810" strokeWidth="1.2" fill="none" />
      {/* Wing */}
      <ellipse cx="36" cy="38" rx="8" ry="5" fill="#E8C020" transform="rotate(-15 36 38)" />
      {/* Coffee mug prop — Central Perk regular */}
      <rect x="44" y="44" width="10" height="10" rx="2" fill="#FAF0E4" stroke="#3D6B4F" strokeWidth="1" />
      <rect x="44" y="48" width="10" height="3" fill="#3D6B4F" />
    </SvgWrap>
  )
}

/** Rachel — fashion & Central Perk waitress apron */
export function RachelCharacterIcon({ className }: IconProps) {
  return (
    <SvgWrap className={className}>
      {/* Hair volume */}
      <path
        d="M18 24 C16 14 24 8 32 8 C40 8 48 14 46 24 C48 28 46 32 44 30 C42 22 36 18 32 18 C28 18 22 22 20 30 C18 32 16 28 18 24 Z"
        fill="#5D4037"
      />
      {/* Face */}
      <circle cx="32" cy="32" r="10" fill="#F4C9A8" />
      {/* Green Central Perk apron */}
      <path d="M20 38 L44 38 L42 58 L22 58 Z" fill="#3D6B4F" stroke="#2D5016" strokeWidth="1" />
      <path d="M26 38 L32 44 L38 38" fill="#FAF0E4" opacity="0.3" />
      {/* Handbag */}
      <rect x="46" y="42" width="10" height="12" rx="2" fill="#E63946" stroke="#B71C1C" strokeWidth="1" />
      <path d="M48 42 Q51 38 54 42" stroke="#B71C1C" strokeWidth="1.5" fill="none" />
    </SvgWrap>
  )
}

const CHARACTER_ICONS: Record<string, FC<IconProps>> = {
  ross: RossCharacterIcon,
  monica: MonicaCharacterIcon,
  phoebe: PhoebeCharacterIcon,
  joey: JoeyCharacterIcon,
  chandler: ChandlerCharacterIcon,
  rachel: RachelCharacterIcon,
}

export function CharacterIconArt({
  characterId,
  className = 'w-full h-full',
}: {
  characterId: string
  className?: string
}) {
  const Icon = CHARACTER_ICONS[characterId] ?? RossCharacterIcon
  return <Icon className={className} />
}
