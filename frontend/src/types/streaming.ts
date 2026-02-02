/**
 * Streaming Visualization Types
 * Types for 2.5D animations and streaming visualization system
 */

// Animation phases matching SSE events
export type AnimationPhase =
  | 'idle'
  | 'connecting'
  | 'thinking'
  | 'tool_executing'
  | 'revealing'
  | 'complete'
  | 'error'

// Intensity levels for animations
export type IntensityLevel = 'low' | 'medium' | 'high'

// Particle types
export type ParticleType = 'sparkle' | 'star' | 'bubble' | 'confetti'

// Particle behavior
export type ParticleBehavior = 'rise' | 'fall' | 'drift' | 'burst' | 'float'

// Depth layer configuration
export interface DepthConfig {
  layer: 'background' | 'midground' | 'foreground'
  parallaxFactor: number // 0-1, how much the layer moves
  scale?: number
  blur?: number
  opacity?: number
}

// Particle configuration
export interface ParticleConfig {
  type: ParticleType
  behavior: ParticleBehavior
  count: number
  colors: string[]
  size: {
    min: number
    max: number
  }
  speed: {
    min: number
    max: number
  }
  lifetime: number // ms
  spread: number // degrees
}

// Phase-specific animation configuration
export interface PhaseAnimationConfig {
  phase: AnimationPhase
  particles?: ParticleConfig
  backgroundColor?: string
  backgroundGradient?: string
  iconAnimation?: {
    icon: string
    animation: 'bounce' | 'pulse' | 'spin' | 'shake'
  }
  soundEffect?: string
  intensity: IntensityLevel
  duration?: number
}

// Stream visualization context value
export interface StreamVisualizationContextValue {
  // Current state
  phase: AnimationPhase
  intensity: IntensityLevel
  isAnimating: boolean
  message: string
  thinkingContent: string
  currentTool: string | null

  // Mouse/scroll tracking for parallax
  mousePosition: { x: number; y: number }
  scrollPosition: number

  // Reduced motion preference
  prefersReducedMotion: boolean

  // Actions
  setPhase: (phase: AnimationPhase) => void
  setIntensity: (intensity: IntensityLevel) => void
  setMessage: (message: string) => void
  setThinkingContent: (content: string) => void
  setCurrentTool: (tool: string | null) => void
  triggerEffect: (effect: 'confetti' | 'sparkles' | 'stars') => void
  reset: () => void
}

// Parallax configuration
export interface ParallaxConfig {
  enabled: boolean
  intensity: number // 0-1
  smoothing: number // 0-1, lower = smoother
  maxRotation: number // degrees
  maxTranslation: number // pixels
  perspective: number // pixels
}

// Tilt configuration for cards
export interface TiltConfig {
  enabled: boolean
  maxTilt: number // degrees
  scale: number // hover scale
  speed: number // ms
  glare: boolean
  glareMaxOpacity: number
}

// Effect trigger event
export interface EffectTrigger {
  type: 'confetti' | 'sparkles' | 'stars' | 'burst'
  origin?: { x: number; y: number }
  count?: number
  duration?: number
  colors?: string[]
}

// Animation preset for a specific phase
export interface AnimationPreset {
  phase: AnimationPhase
  enter: {
    opacity: number
    scale: number
    y: number
    transition: {
      duration: number
      ease: string
    }
  }
  animate: {
    opacity: number
    scale: number
    y: number
    transition?: {
      duration?: number
      repeat?: number
      repeatType?: 'loop' | 'reverse' | 'mirror'
    }
  }
  exit: {
    opacity: number
    scale: number
    y: number
    transition: {
      duration: number
    }
  }
}

// Sound effect configuration
export interface SoundConfig {
  src: string
  volume: number
  playbackRate?: number
}

// Theme colors for phases
export interface PhaseColors {
  primary: string
  secondary: string
  accent: string
  background: string
  text: string
  glow: string
}

// Complete phase theme
export interface PhaseTheme {
  colors: PhaseColors
  particles: ParticleConfig
  animation: AnimationPreset
  sound?: SoundConfig
  icon: string
  label: string
}
