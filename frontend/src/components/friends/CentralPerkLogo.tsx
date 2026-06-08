import { CentralPerkFriendsTitle } from '@/components/friends/FriendsLogo'

interface Props {
  size?: number
  /** Friends-style CENTRAL PERK title above the couch */
  showTitle?: boolean
  /** Title colors — light for purple backgrounds, dark for cream/white */
  titleVariant?: 'light' | 'dark'
  className?: string
}

function titleSizeForLogo(size: number): 'xs' | 'sm' | 'md' | 'lg' {
  if (size <= 40) return 'xs'
  if (size <= 56) return 'sm'
  if (size <= 80) return 'md'
  return 'lg'
}

/** Simple orange couch + Friends-style Central Perk title */
export function CentralPerkLogo({
  size = 64,
  showTitle = true,
  titleVariant = 'light',
  className = '',
}: Props) {
  const couchH = size
  const couchW = Math.round(size * 1.35)
  const titleSize = titleSizeForLogo(size)

  return (
    <div className={`inline-flex flex-col items-center gap-1 ${className}`}>
      {showTitle && (
        <CentralPerkFriendsTitle size={titleSize} variant={titleVariant} />
      )}

      <svg
        width={couchW}
        height={couchH}
        viewBox="0 0 108 58"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="centralperk-couch"
        aria-hidden
      >
        {/* Yellow frame — Monica's door nod */}
        <rect
          x="2"
          y="4"
          width="104"
          height="50"
          rx="8"
          stroke="#F4D03F"
          strokeWidth="2.5"
          fill="none"
          opacity="0.85"
          className="couch-frame"
        />

        <ellipse cx="54" cy="52" rx="42" ry="4" fill="#4A2870" opacity="0.12" className="couch-shadow" />

        {/* Back rest */}
        <path
          d="M12 28 C12 16 22 10 54 10 C86 10 96 16 96 28 L96 36 L12 36 Z"
          fill="#C85018"
          className="couch-back"
        />
        <path
          d="M16 28 C16 18 26 14 54 14 C82 14 92 18 92 28 L92 32 L16 32 Z"
          fill="#E8751A"
        />

        {/* Arm rests */}
        <rect x="8" y="28" width="12" height="18" rx="6" fill="#B84510" />
        <rect x="88" y="28" width="12" height="18" rx="6" fill="#B84510" />
        <rect x="10" y="30" width="8" height="14" rx="4" fill="#E8751A" />
        <rect x="90" y="30" width="8" height="14" rx="4" fill="#E8751A" />

        {/* Seat cushions */}
        <rect x="22" y="36" width="28" height="12" rx="5" fill="#D96014" className="couch-cushion-left" />
        <rect x="58" y="36" width="28" height="12" rx="5" fill="#D96014" className="couch-cushion-right" />
        <rect x="24" y="38" width="24" height="8" rx="4" fill="#F09030" opacity="0.55" />
        <rect x="60" y="38" width="24" height="8" rx="4" fill="#F09030" opacity="0.55" />
      </svg>
    </div>
  )
}
