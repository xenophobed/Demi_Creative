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

  // 清理函数
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

  // 初始化音频
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
        options?.onLoad?.()

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
        options?.onEnd?.()
      },
      onloaderror: (_id, error) => {
        setState(prev => ({ ...prev, isLoading: false }))
        options?.onError?.(String(error) || 'Audio failed to load')
      },
      onplayerror: (_id, error) => {
        setState(prev => ({ ...prev, isPlaying: false }))
        options?.onError?.(String(error) || 'Audio failed to play')
      },
    })

    soundRef.current = sound

    return cleanup
  }, [src, cleanup, options?.autoPlay])

  // 更新播放进度
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

  // 播放
  const play = useCallback(() => {
    if (soundRef.current) {
      soundRef.current.play()
      setState(prev => ({ ...prev, isPlaying: true }))
    }
  }, [])

  // 暂停
  const pause = useCallback(() => {
    if (soundRef.current) {
      soundRef.current.pause()
      setState(prev => ({ ...prev, isPlaying: false }))
    }
  }, [])

  // 切换播放/暂停
  const toggle = useCallback(() => {
    if (state.isPlaying) {
      pause()
    } else {
      play()
    }
  }, [state.isPlaying, play, pause])

  // 跳转到指定时间
  const seek = useCallback((time: number) => {
    if (soundRef.current) {
      soundRef.current.seek(time)
      setState(prev => ({ ...prev, currentTime: time }))
    }
  }, [])

  // 停止并重置
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

  // 设置音量 (0-1)
  const setVolume = useCallback((volume: number) => {
    if (soundRef.current) {
      soundRef.current.volume(Math.max(0, Math.min(1, volume)))
    }
  }, [])

  // 格式化时间
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
