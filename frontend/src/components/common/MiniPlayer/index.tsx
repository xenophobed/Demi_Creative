import { useAudio } from '@/contexts/AudioContext'

interface MiniPlayerProps {
  itemId: string
  audioUrl: string
}

const SIZE = 36
const STROKE = 3
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export default function MiniPlayer({ itemId, audioUrl }: MiniPlayerProps) {
  const { currentId, isPlaying, progress, play } = useAudio()
  const active = currentId === itemId
  const playing = active && isPlaying
  const dashOffset = CIRCUMFERENCE * (1 - (active ? progress : 0))

  return (
    <button
      className="relative flex items-center justify-center transition-transform hover:scale-110 active:scale-95"
      style={{ width: SIZE, height: SIZE }}
      onClick={(e) => {
        e.stopPropagation()
        play(itemId, audioUrl)
      }}
      title={playing ? 'Pause' : 'Play'}
    >
      {/* Progress ring */}
      <svg
        className="absolute inset-0"
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
      >
        {/* Background circle */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="currentColor"
          strokeWidth={STROKE}
          className="text-gray-200"
        />
        {/* Progress arc */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="currentColor"
          strokeWidth={STROKE}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          className="text-secondary transition-[stroke-dashoffset] duration-100"
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
      </svg>

      {/* Play / Pause icon */}
      <span className="relative z-10 text-gray-600">
        {playing ? (
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="4" width="4" height="16" rx="1" />
            <rect x="14" y="4" width="4" height="16" rx="1" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5,3 19,12 5,21" />
          </svg>
        )}
      </span>
    </button>
  )
}
