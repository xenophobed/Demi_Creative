import { useState, useEffect, useCallback, useRef } from 'react'
import { Howl } from 'howler'
import type { AudioState } from '@/types/api'

interface UseAudioPlayerOptions {
  autoPlay?: boolean
  onEnd?: () => void
  onLoad?: () => void
  onError?: (error: string) => void
}

export function useAudioPlayer(src: string | null, options?: UseAudioPlayerOptions) {
  const [state, setState] = useState<AudioState>({
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    isLoading: false,
  })

  const soundRef = useRef<Howl | null>(null)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const onEndRef = useRef(options?.onEnd)
  const onLoadRef = useRef(options?.onLoad)
  const onErrorRef = useRef(options?.onError)

  useEffect(() => {
    onEndRef.current = options?.onEnd
    onLoadRef.current = options?.onLoad
    onErrorRef.current = options?.onError
  }, [options?.onEnd, options?.onLoad, options?.onError])

  // Cleanup function
  const cleanup = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (soundRef.current) {
      soundRef.current.unload()
      soundRef.current = null
    }
  }, [])

  // Initialize audio
  useEffect(() => {
    if (!src) {
      cleanup()
      setState({
        isPlaying: false,
        currentTime: 0,
        duration: 0,
        isLoading: false,
      })
      return
    }

    setState(prev => ({ ...prev, isLoading: true }))

    const sound = new Howl({
      src: [src],
      html5: true,
      onload: () => {
        setState(prev => ({
          ...prev,
          duration: sound.duration(),
          isLoading: false,
        }))
        onLoadRef.current?.()

        if (options?.autoPlay) {
          sound.play()
          setState(prev => ({ ...prev, isPlaying: true }))
        }
      },
      onend: () => {
        setState(prev => ({
          ...prev,
          isPlaying: false,
          currentTime: 0,
        }))
        onEndRef.current?.()
      },
      onloaderror: (_id, error) => {
        setState(prev => ({ ...prev, isLoading: false }))
        onErrorRef.current?.(String(error) || 'Audio failed to load')
      },
      onplayerror: (_id, error) => {
        setState(prev => ({ ...prev, isPlaying: false }))
        onErrorRef.current?.(String(error) || 'Audio failed to play')
      },
    })

    soundRef.current = sound

    return cleanup
  }, [src, cleanup, options?.autoPlay])

  // Update playback progress
  useEffect(() => {
    if (!soundRef.current || !state.isPlaying) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }

    intervalRef.current = setInterval(() => {
      if (soundRef.current) {
        const seek = soundRef.current.seek()
        if (typeof seek === 'number') {
          setState(prev => ({ ...prev, currentTime: seek }))
        }
      }
    }, 100)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [state.isPlaying])

  // Play
  const play = useCallback(() => {
    if (soundRef.current) {
      soundRef.current.play()
      setState(prev => ({ ...prev, isPlaying: true }))
    }
  }, [])

  // Pause
  const pause = useCallback(() => {
    if (soundRef.current) {
      soundRef.current.pause()
      setState(prev => ({ ...prev, isPlaying: false }))
    }
  }, [])

  // Toggle play/pause
  const toggle = useCallback(() => {
    if (state.isPlaying) {
      pause()
    } else {
      play()
    }
  }, [state.isPlaying, play, pause])

  // Seek to specific time
  const seek = useCallback((time: number) => {
    if (soundRef.current) {
      soundRef.current.seek(time)
      setState(prev => ({ ...prev, currentTime: time }))
    }
  }, [])

  // Stop and reset
  const stop = useCallback(() => {
    if (soundRef.current) {
      soundRef.current.stop()
      setState(prev => ({
        ...prev,
        isPlaying: false,
        currentTime: 0,
      }))
    }
  }, [])

  // Set volume (0-1)
  const setVolume = useCallback((volume: number) => {
    if (soundRef.current) {
      soundRef.current.volume(Math.max(0, Math.min(1, volume)))
    }
  }, [])

  // Format time
  const formatTime = useCallback((seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }, [])

  return {
    ...state,
    play,
    pause,
    toggle,
    seek,
    stop,
    setVolume,
    formatTime,
    formattedCurrentTime: formatTime(state.currentTime),
    formattedDuration: formatTime(state.duration),
    progress: state.duration > 0 ? state.currentTime / state.duration : 0,
  }
}

export default useAudioPlayer
