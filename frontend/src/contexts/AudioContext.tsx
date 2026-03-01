import { createContext, useContext, useCallback, useRef, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { Howl } from 'howler'

interface AudioState {
  currentId: string | null
  isPlaying: boolean
  progress: number // 0-1
  play: (id: string, src: string) => void
  pause: () => void
  stop: () => void
}

const AudioCtx = createContext<AudioState>({
  currentId: null,
  isPlaying: false,
  progress: 0,
  play: () => {},
  pause: () => {},
  stop: () => {},
})

export function useAudio() {
  return useContext(AudioCtx)
}

export function AudioProvider({ children }: { children: ReactNode }) {
  const howlRef = useRef<Howl | null>(null)
  const rafRef = useRef<number>(0)
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [progress, setProgress] = useState(0)

  const cleanup = useCallback(() => {
    if (howlRef.current) {
      howlRef.current.stop()
      howlRef.current.unload()
      howlRef.current = null
    }
    cancelAnimationFrame(rafRef.current)
    setIsPlaying(false)
    setProgress(0)
  }, [])

  const updateProgress = useCallback(() => {
    const h = howlRef.current
    if (h && h.playing()) {
      const seek = h.seek() as number
      const dur = h.duration()
      setProgress(dur > 0 ? seek / dur : 0)
      rafRef.current = requestAnimationFrame(updateProgress)
    }
  }, [])

  const play = useCallback(
    (id: string, src: string) => {
      // If same track, toggle play/pause
      if (currentId === id && howlRef.current) {
        if (howlRef.current.playing()) {
          howlRef.current.pause()
          setIsPlaying(false)
          cancelAnimationFrame(rafRef.current)
        } else {
          howlRef.current.play()
          setIsPlaying(true)
          rafRef.current = requestAnimationFrame(updateProgress)
        }
        return
      }

      // Stop previous audio
      cleanup()

      const howl = new Howl({
        src: [src.startsWith('/') ? src : '/' + src],
        html5: true,
        onplay: () => {
          setIsPlaying(true)
          rafRef.current = requestAnimationFrame(updateProgress)
        },
        onpause: () => setIsPlaying(false),
        onstop: () => {
          setIsPlaying(false)
          setProgress(0)
        },
        onend: () => {
          setIsPlaying(false)
          setProgress(1)
          cancelAnimationFrame(rafRef.current)
        },
      })

      howlRef.current = howl
      setCurrentId(id)
      howl.play()
    },
    [currentId, cleanup, updateProgress]
  )

  const pause = useCallback(() => {
    howlRef.current?.pause()
    cancelAnimationFrame(rafRef.current)
  }, [])

  const stop = useCallback(() => {
    cleanup()
    setCurrentId(null)
  }, [cleanup])

  // Cleanup on unmount
  useEffect(() => () => cleanup(), [cleanup])

  return (
    <AudioCtx.Provider value={{ currentId, isPlaying, progress, play, pause, stop }}>
      {children}
    </AudioCtx.Provider>
  )
}
