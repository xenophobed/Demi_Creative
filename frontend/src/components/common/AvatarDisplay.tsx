import { resolveMediaUrl } from '@/utils/mediaUrl'

const SIZE_CLASSES = {
  sm: 'w-8 h-8 text-lg',
  md: 'w-12 h-12 text-2xl',
  lg: 'w-16 h-16 text-3xl',
} as const

type AvatarSize = keyof typeof SIZE_CLASSES

interface AvatarDisplayProps {
  avatarUrl?: string | null
  size?: AvatarSize
  className?: string
}

/**
 * Renders a user avatar — emoji, image URL, or default fallback.
 * Detects `emoji:🐼` prefix and renders as large emoji span.
 */
function AvatarDisplay({ avatarUrl, size = 'md', className = '' }: AvatarDisplayProps) {
  const sizeClass = SIZE_CLASSES[size]

  // Emoji avatar: stored as "emoji:🐼"
  if (avatarUrl?.startsWith('emoji:')) {
    const emoji = avatarUrl.slice(6)
    return (
      <div
        className={`${sizeClass} rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center flex-shrink-0 ${className}`}
      >
        {emoji}
      </div>
    )
  }

  // Image URL avatar
  if (avatarUrl) {
    return (
      <div className={`${sizeClass} rounded-full overflow-hidden flex-shrink-0 ${className}`}>
        <img
          src={resolveMediaUrl(avatarUrl) || avatarUrl}
          alt="avatar"
          className="w-full h-full object-cover"
        />
      </div>
    )
  }

  // Default fallback
  return (
    <div
      className={`${sizeClass} rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center flex-shrink-0 ${className}`}
    >
      👤
    </div>
  )
}

export default AvatarDisplay
