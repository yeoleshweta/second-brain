import { APP_BRAND, CENTRAL_PERK } from '@/theme/friends'
import { CentralPerkLogo } from '@/components/friends/CentralPerkLogo'

interface Props {
  compact?: boolean
  hero?: boolean
  /** Starts a new chat; previous conversation stays in Recent chats. */
  onLogoClick?: () => void
}

function LogoHitTarget({
  onClick,
  children,
  className = '',
}: {
  onClick?: () => void
  children: React.ReactNode
  className?: string
}) {
  if (!onClick) return <>{children}</>
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl transition active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-friends-frame/80 ${className}`}
      aria-label="Start new chat"
      title="New chat"
    >
      {children}
    </button>
  )
}

/** Branded header — Friends-style title + orange couch */
export function FriendsDoorHeader({ compact = false, hero = false, onLogoClick }: Props) {
  if (compact) {
    return (
      <LogoHitTarget onClick={onLogoClick}>
        <CentralPerkLogo size={40} showTitle titleVariant="dark" />
      </LogoHitTarget>
    )
  }

  if (hero) {
    return (
      <div
        className="relative overflow-hidden rounded-2xl md:rounded-3xl p-5 md:p-7 shadow-card-lg text-white text-center"
        style={{
          background: 'linear-gradient(145deg, #6B3FA0 0%, #4A2870 50%, #9B6BC4 100%)',
        }}
      >
        <LogoHitTarget onClick={onLogoClick} className="mx-auto inline-block hover:opacity-95">
          <CentralPerkLogo size={80} showTitle titleVariant="light" className="md:hidden" />
          <CentralPerkLogo size={96} showTitle titleVariant="light" className="hidden md:block" />
        </LogoHitTarget>
        <p className="text-[11px] md:text-xs text-white/70 mt-3 italic">{CENTRAL_PERK.tagline}</p>
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-friends-purple to-friends-purple-dark p-4 shadow-card-lg text-white">
      <LogoHitTarget onClick={onLogoClick} className="mx-auto flex justify-center hover:opacity-95">
        <CentralPerkLogo size={56} showTitle titleVariant="light" />
      </LogoHitTarget>
      <p className="text-[10px] text-friends-frame mt-2 text-center italic">{APP_BRAND.tagline}</p>
    </div>
  )
}

/** Subtle apartment wallpaper pattern for page backgrounds */
export function FriendsBackground() {
  return (
    <div
      className="pointer-events-none fixed inset-0 -z-10 opacity-[0.35]"
      aria-hidden
      style={{
        backgroundImage: `
          radial-gradient(circle at 20% 80%, rgba(107, 63, 160, 0.08) 0%, transparent 45%),
          radial-gradient(circle at 80% 20%, rgba(232, 117, 26, 0.06) 0%, transparent 40%),
          repeating-linear-gradient(
            90deg,
            transparent,
            transparent 48px,
            rgba(244, 208, 63, 0.03) 48px,
            rgba(244, 208, 63, 0.03) 49px
          )
        `,
      }}
    />
  )
}
