import { resolveMediaUrl } from '@/utils/mediaUrl'

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

  // Emoji avatar: stored as "emoji:<emoji>"
  if (avatarUrl && avatarUrl.startsWith('emoji:')) {
    const emoji = avatarUrl.slice('emoji:'.length)
    return (
      <div
        className={`${sizeClasses} rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center flex-shrink-0 ${className}`}
      >
        <span>{emoji}</span>
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
      className={`${sizeClasses} rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center flex-shrink-0 ${className}`}
    >
      <span>👤</span>
    </div>
  )
}

export default AvatarDisplay
