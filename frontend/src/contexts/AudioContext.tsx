import { createContext, useContext, useCallback, useRef, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { Howl } from 'howler'
import { resolveMediaUrl } from '@/utils/mediaUrl'

interface AudioState {
  currentId: string | null
  isPlaying: boolean
  progress: number // 0-1
  // `src` may be a single URL or an ordered playlist (e.g. a multi-segment
  // Kids Daily show); a playlist plays each clip back-to-back as one track.
  play: (id: string, src: string | string[]) => void
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
  // Playlist state for multi-segment tracks: ordered srcs + the index playing now.
  const playlistRef = useRef<string[]>([])
  const playlistIndexRef = useRef<number>(0)
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
    playlistRef.current = []
    playlistIndexRef.current = 0
    setIsPlaying(false)
    setProgress(0)
  }, [])

  const updateProgress = useCallback(() => {
    const h = howlRef.current
    if (h && h.playing()) {
      const seek = h.seek() as number
      const dur = h.duration()
      // Spread progress across the whole playlist so the ring reflects the full
      // show, not just the current clip. Clip durations differ, but treating
      // each clip as an equal slice is a good-enough approximation for the ring.
      const total = playlistRef.current.length || 1
      const clipFraction = dur > 0 ? seek / dur : 0
      setProgress((playlistIndexRef.current + clipFraction) / total)
      rafRef.current = requestAnimationFrame(updateProgress)
    }
  }, [])

  // Load + play one clip of the active playlist. When a clip ends, advance to
  // the next; the last clip finishing ends the whole track.
  const playClip = useCallback(
    (index: number) => {
      const playlist = playlistRef.current
      const raw = playlist[index]
      const resolvedSrc = raw ? resolveMediaUrl(raw) : null
      if (!resolvedSrc) {
        cleanup()
        return
      }

      playlistIndexRef.current = index

      const howl = new Howl({
        src: [resolvedSrc],
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
          cancelAnimationFrame(rafRef.current)
          const next = playlistIndexRef.current + 1
          if (next < playlistRef.current.length) {
            howlRef.current?.unload()
            playClip(next)
          } else {
            setIsPlaying(false)
            setProgress(1)
          }
        },
      })

      howlRef.current = howl
      howl.play()
    },
    [cleanup, updateProgress]
  )

  const play = useCallback(
    (id: string, src: string | string[]) => {
      const playlist = (Array.isArray(src) ? src : [src]).filter(Boolean)
      if (playlist.length === 0) {
        return
      }

      // If same track, toggle play/pause (resumes the same clip in a playlist).
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

      // Stop previous audio and start the new track from its first clip.
      cleanup()
      playlistRef.current = playlist
      setCurrentId(id)
      playClip(0)
    },
    [currentId, cleanup, updateProgress, playClip]
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
