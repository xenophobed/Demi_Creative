import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Howl } from 'howler'

interface AudioPlayerProps {
  src: string | null
  title?: string
  autoPlay?: boolean
  onEnd?: () => void
  className?: string
}

function AudioPlayer({
  src,
  title = 'Story Narration',
  autoPlay = false,
  onEnd,
  className = '',
}: AudioPlayerProps) {
  const [sound, setSound] = useState<Howl | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [isLoading, setIsLoading] = useState(false)

  // Initialize audio
  useEffect(() => {
    if (!src) return

    setIsLoading(true)
    const newSound = new Howl({
      src: [src],
      html5: true,
      onload: () => {
        setDuration(newSound.duration())
        setIsLoading(false)
        if (autoPlay) {
          newSound.play()
          setIsPlaying(true)
        }
      },
      onend: () => {
        setIsPlaying(false)
        setCurrentTime(0)
        onEnd?.()
      },
      onloaderror: () => {
        setIsLoading(false)
        console.error('Audio failed to load')
      },
    })

    setSound(newSound)

    return () => {
      newSound.unload()
    }
  }, [src, autoPlay, onEnd])

  // Update playback progress
  useEffect(() => {
    if (!sound || !isPlaying) return

    const interval = setInterval(() => {
      setCurrentTime(sound.seek() as number)
    }, 100)

    return () => clearInterval(interval)
  }, [sound, isPlaying])

  const togglePlay = useCallback(() => {
    if (!sound) return

    if (isPlaying) {
      sound.pause()
      setIsPlaying(false)
    } else {
      sound.play()
      setIsPlaying(true)
    }
  }, [sound, isPlaying])

  const handleSeek = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!sound) return
      const time = parseFloat(e.target.value)
      sound.seek(time)
      setCurrentTime(time)
    },
    [sound]
  )

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (!src) {
    return (
      <div className={`bg-gray-100 rounded-card p-4 text-center text-gray-500 ${className}`}>
        No audio available
      </div>
    )
  }

  return (
    <motion.div
      className={`bg-gradient-to-r from-primary/10 to-secondary/10 rounded-card p-4 ${className}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      {/* Title */}
      <div className="flex items-center gap-2 mb-3">
        <SpeakerIcon className="w-5 h-5 text-primary" />
        <span className="font-medium text-gray-700">{title}</span>
      </div>

      <div className="flex items-center gap-4">
        {/* Play button */}
        <motion.button
          className={`w-12 h-12 rounded-full flex items-center justify-center
            ${isPlaying ? 'bg-primary' : 'bg-secondary'} text-white
            shadow-lg`}
          onClick={togglePlay}
          disabled={isLoading}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
        >
          {isLoading ? (
            <LoadingIcon />
          ) : isPlaying ? (
            <PauseIcon />
          ) : (
            <PlayIcon />
          )}
        </motion.button>

        {/* Progress bar and time */}
        <div className="flex-1">
          <input
            type="range"
            min={0}
            max={duration}
            value={currentTime}
            onChange={handleSeek}
            className="w-full h-2 bg-gray-200 rounded-full appearance-none cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none
              [&::-webkit-slider-thumb]:w-4
              [&::-webkit-slider-thumb]:h-4
              [&::-webkit-slider-thumb]:rounded-full
              [&::-webkit-slider-thumb]:bg-primary
              [&::-webkit-slider-thumb]:cursor-pointer
              [&::-webkit-slider-thumb]:shadow-md"
            style={{
              background: `linear-gradient(to right, #FF6B6B ${(currentTime / duration) * 100}%, #e5e7eb ${(currentTime / duration) * 100}%)`,
            }}
          />
          <div className="flex justify-between mt-1 text-sm text-gray-500">
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>
      </div>

      {/* Sound wave animation */}
      {isPlaying && (
        <div className="flex justify-center gap-1 mt-3">
          {[...Array(5)].map((_, i) => (
            <motion.div
              key={i}
              className="w-1 bg-primary rounded-full"
              animate={{
                height: [8, 20, 8],
              }}
              transition={{
                duration: 0.5,
                repeat: Infinity,
                delay: i * 0.1,
              }}
            />
          ))}
        </div>
      )}
    </motion.div>
  )
}

// Icons
function PlayIcon() {
  return (
    <svg className="w-6 h-6 ml-1" fill="currentColor" viewBox="0 0 24 24">
      <path d="M8 5v14l11-7z" />
    </svg>
  )
}

function PauseIcon() {
  return (
    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
      <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
    </svg>
  )
}

function LoadingIcon() {
  return (
    <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

function SpeakerIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 24 24">
      <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
    </svg>
  )
}

export default AudioPlayer
