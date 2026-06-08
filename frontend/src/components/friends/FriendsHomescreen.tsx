import { useState } from 'react'
import { AGENTS, type AgentDef } from '@/agents'
import { AGENT_CHARACTER_MAP, FRIENDS_CHARACTERS } from '@/theme/friends'
import { CharacterIconArt } from '@/components/friends/CharacterIcons'

interface Props {
  agent: AgentDef
  onTap?: () => void
  dimmed?: boolean
}

/** iOS / Widgetsmith squircle app icon for one Friend */
export function FriendAppIcon({ agent, onTap, dimmed = false }: Props) {
  const charKey = AGENT_CHARACTER_MAP[agent.id] ?? 'ross'
  const character = FRIENDS_CHARACTERS[charKey]
  const [imgFailed, setImgFailed] = useState(false)
  const showImage = character.avatarAsset && !imgFailed

  const icon = (
    <div
      className={`relative w-[68px] h-[68px] sm:w-[58px] sm:h-[58px] rounded-[22%] flex items-center justify-center shadow-card-lg border border-white/20 ${character.avatarBg} ${dimmed ? 'opacity-45 grayscale-[30%]' : ''}`}
      style={{ boxShadow: '0 4px 14px rgba(74, 40, 112, 0.25)' }}
    >
      {showImage ? (
        <img
          src={character.avatarAsset}
          alt={agent.name}
          className="w-full h-full rounded-[22%] object-cover"
          onError={() => setImgFailed(true)}
        />
      ) : (
        <CharacterIconArt characterId={charKey} className="w-[88%] h-[88%]" />
      )}
    </div>
  )

  const label = (
    <span className="text-[10px] font-medium text-paper-700 mt-1.5 max-w-[64px] truncate text-center block">
      {agent.name}
    </span>
  )

  if (onTap) {
    return (
      <button
        type="button"
        onClick={onTap}
        className="flex flex-col items-center min-w-[76px] min-h-[88px] justify-center active:scale-95 transition-transform touch-manipulation"
      >
        {icon}
        {label}
      </button>
    )
  }

  return (
    <div className="flex flex-col items-center min-w-[64px]">
      {icon}
      {label}
    </div>
  )
}

interface GridProps {
  onAgentTap?: (agent: AgentDef) => void
}

/** Pinterest / Widgetsmith-style 3×2 character homescreen grid */
export function FriendsHomescreenGrid({ onAgentTap }: GridProps) {
  return (
    <div className="grid grid-cols-3 gap-x-3 gap-y-4 sm:gap-x-4 sm:gap-y-5 justify-items-center py-1 sm:py-2">
      {AGENTS.map((agent) => (
        <FriendAppIcon
          key={agent.id}
          agent={agent}
          dimmed={!agent.live}
          onTap={onAgentTap ? () => onAgentTap(agent) : undefined}
        />
      ))}
    </div>
  )
}
