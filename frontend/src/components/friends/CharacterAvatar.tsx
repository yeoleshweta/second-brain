import { useState } from 'react'
import { AGENT_CHARACTER_MAP, FRIENDS_CHARACTERS, type CharacterTheme } from '@/theme/friends'
import { CharacterIconArt } from '@/components/friends/CharacterIcons'

interface Props {
  character: CharacterTheme
  size?: 'sm' | 'md' | 'lg'
  framed?: boolean
  className?: string
}

const SIZES = {
  sm: { box: 'w-8 h-8 text-base', frame: 'p-0.5' },
  md: { box: 'w-10 h-10 text-xl', frame: 'p-0.5' },
  lg: { box: 'w-12 h-12 text-2xl', frame: 'p-1' },
} as const

export function CharacterAvatar({
  character,
  size = 'md',
  framed = true,
  className = '',
}: Props) {
  const s = SIZES[size]
  const charKey = Object.entries(FRIENDS_CHARACTERS).find(([, c]) => c.id === character.id)?.[0] ?? 'ross'
  const [imgFailed, setImgFailed] = useState(false)
  const showImage = character.avatarAsset && !imgFailed

  const inner = (
    <div
      className={`relative ${s.box} rounded-xl flex items-center justify-center shrink-0 shadow-card overflow-hidden ${character.avatarBg} ${className}`}
      title={character.name}
    >
      {showImage ? (
        <img
          src={character.avatarAsset}
          alt={character.name}
          className="w-full h-full object-cover"
          onError={() => setImgFailed(true)}
        />
      ) : (
        <CharacterIconArt characterId={charKey} className="w-[85%] h-[85%]" />
      )}
    </div>
  )

  if (!framed) return inner

  return (
    <div
      className={`rounded-[14px] bg-friends-frame ${s.frame} shadow-card`}
      style={{ boxShadow: '0 2px 8px rgba(107, 63, 160, 0.15)' }}
    >
      {inner}
    </div>
  )
}

export function CharacterAvatarByAgentId({
  agentId,
  ...props
}: Omit<Props, 'character'> & { agentId: string }) {
  const key = AGENT_CHARACTER_MAP[agentId] ?? 'ross'
  return <CharacterAvatar character={FRIENDS_CHARACTERS[key]} {...props} />
}
