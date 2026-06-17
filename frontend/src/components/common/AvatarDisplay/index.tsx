import { resolveMediaUrl } from '@/utils/mediaUrl'
import { UserRound } from 'lucide-react'
import { AnimalAvatarIcon, isAnimalAvatarId } from '@/lib/avatarIcons'

const sizeMap = {
  sm: 'w-8 h-8 text-lg',
  md: 'w-12 h-12 text-2xl',
  lg: 'w-16 h-16 text-3xl',
} as const

interface AvatarDisplayProps {
  avatarUrl: string | null | undefined
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

function AvatarDisplay({ avatarUrl, size = 'md', className = '' }: AvatarDisplayProps) {
  const sizeClasses = sizeMap[size]

  // Animal avatar ids stay in storage for compatibility, while the UI renders
  // the matching flat animal icon.
  if (isAnimalAvatarId(avatarUrl)) {
    return (
      <div
        className={`${sizeClasses} rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center flex-shrink-0 text-primary ${className}`}
      >
        <AnimalAvatarIcon avatarId={avatarUrl} size={size === 'sm' ? 16 : size === 'lg' ? 28 : 22} />
      </div>
    )
  }

  // URL avatar
  if (avatarUrl) {
    const resolved = resolveMediaUrl(avatarUrl)
    if (resolved) {
      return (
        <div
          className={`${sizeClasses} rounded-full overflow-hidden flex-shrink-0 ${className}`}
        >
          <img
            src={resolved}
            alt="avatar"
            className="w-full h-full object-cover"
          />
        </div>
      )
    }
  }

  // Default fallback
  return (
    <div
      className={`${sizeClasses} rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center flex-shrink-0 text-primary ${className}`}
    >
      <UserRound size={size === 'sm' ? 16 : size === 'lg' ? 28 : 22} aria-hidden="true" />
    </div>
  )
}

export default AvatarDisplay
