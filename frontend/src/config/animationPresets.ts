/**
 * Animation Presets Configuration
 * Phase-specific animation configurations for the streaming visualization system
 */

import type {
  AnimationPhase,
  PhaseTheme,
  ParticleConfig,
  AnimationPreset,
  ParallaxConfig,
  TiltConfig,
} from '@/types/streaming'

// Default parallax configuration
export const defaultParallaxConfig: ParallaxConfig = {
  enabled: true,
  intensity: 0.5,
  smoothing: 0.1,
  maxRotation: 8,
  maxTranslation: 20,
  perspective: 1000,
}

// Default tilt configuration for cards
export const defaultTiltConfig: TiltConfig = {
  enabled: true,
  maxTilt: 8,
  scale: 1.02,
  speed: 300,
  glare: true,
  glareMaxOpacity: 0.15,
}

// App color palette
export const colors = {
  primary: '#FF6B6B',
  primaryDark: '#E85555',
  secondary: '#4ECDC4',
  secondaryDark: '#3DBDB4',
  accent: '#FFE66D',
  accentDark: '#E5CC5C',
  warm: '#FFF9F5',
  purple: '#9B59B6',
  yellow: '#F1C40F',
  green: '#2ECC71',
  red: '#E74C3C',
  blue: '#3498DB',
}

// Particle configurations by phase
const particleConfigs: Record<AnimationPhase, ParticleConfig | undefined> = {
  idle: undefined,
  connecting: {
    type: 'bubble',
    behavior: 'float',
    count: 8,
    colors: [colors.primary, colors.secondary, colors.accent],
    size: { min: 4, max: 12 },
    speed: { min: 0.5, max: 1.5 },
    lifetime: 3000,
    spread: 360,
  },
  thinking: {
    type: 'sparkle',
    behavior: 'rise',
    count: 15,
    colors: [colors.purple, '#A855F7', '#C084FC', '#E879F9'],
    size: { min: 6, max: 14 },
    speed: { min: 1, max: 3 },
    lifetime: 2500,
    spread: 45,
  },
  tool_executing: {
    type: 'star',
    behavior: 'burst',
    count: 20,
    colors: [colors.yellow, '#FBBF24', '#FCD34D', colors.accent],
    size: { min: 8, max: 18 },
    speed: { min: 2, max: 5 },
    lifetime: 1500,
    spread: 120,
  },
  revealing: {
    type: 'sparkle',
    behavior: 'drift',
    count: 25,
    colors: [colors.primary, colors.secondary, colors.accent, '#FFF'],
    size: { min: 4, max: 10 },
    speed: { min: 0.5, max: 2 },
    lifetime: 2000,
    spread: 180,
  },
  complete: {
    type: 'confetti',
    behavior: 'fall',
    count: 50,
    colors: [
      colors.primary,
      colors.secondary,
      colors.accent,
      colors.purple,
      colors.green,
      colors.blue,
    ],
    size: { min: 8, max: 16 },
    speed: { min: 3, max: 8 },
    lifetime: 4000,
    spread: 90,
  },
  error: {
    type: 'sparkle',
    behavior: 'drift',
    count: 5,
    colors: [colors.red, '#F87171', '#FCA5A5'],
    size: { min: 4, max: 8 },
    speed: { min: 0.3, max: 1 },
    lifetime: 2000,
    spread: 360,
  },
}

// Animation presets by phase
const animationPresets: Record<AnimationPhase, AnimationPreset> = {
  idle: {
    phase: 'idle',
    enter: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
    animate: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: 0.95, y: 10, transition: { duration: 0.2 } },
  },
  connecting: {
    phase: 'connecting',
    enter: { opacity: 0, scale: 0.9, y: 20, transition: { duration: 0.4, ease: 'easeOut' } },
    animate: {
      opacity: 1,
      scale: 1,
      y: 0,
      transition: { duration: 1.5, repeat: Infinity, repeatType: 'reverse' },
    },
    exit: { opacity: 0, scale: 1.05, y: -10, transition: { duration: 0.3 } },
  },
  thinking: {
    phase: 'thinking',
    enter: { opacity: 0, scale: 0.95, y: 10, transition: { duration: 0.3, ease: 'easeOut' } },
    animate: {
      opacity: 1,
      scale: 1,
      y: 0,
      transition: { duration: 2, repeat: Infinity, repeatType: 'reverse' },
    },
    exit: { opacity: 0, scale: 1.02, y: -5, transition: { duration: 0.25 } },
  },
  tool_executing: {
    phase: 'tool_executing',
    enter: { opacity: 0, scale: 0.8, y: 0, transition: { duration: 0.3, ease: 'backOut' } },
    animate: {
      opacity: 1,
      scale: 1,
      y: 0,
      transition: { duration: 0.5, repeat: Infinity, repeatType: 'reverse' },
    },
    exit: { opacity: 0, scale: 1.1, y: 0, transition: { duration: 0.2 } },
  },
  revealing: {
    phase: 'revealing',
    enter: { opacity: 0, scale: 0.9, y: 30, transition: { duration: 0.5, ease: 'easeOut' } },
    animate: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: 0.95, y: -10, transition: { duration: 0.3 } },
  },
  complete: {
    phase: 'complete',
    enter: { opacity: 0, scale: 0.8, y: 20, transition: { duration: 0.5, ease: 'backOut' } },
    animate: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: 0.9, y: 10, transition: { duration: 0.3 } },
  },
  error: {
    phase: 'error',
    enter: { opacity: 0, scale: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
    animate: {
      opacity: 1,
      scale: 1,
      y: 0,
      transition: { duration: 0.1, repeat: 3, repeatType: 'reverse' },
    },
    exit: { opacity: 0, scale: 0.95, y: 5, transition: { duration: 0.2 } },
  },
}

// Complete phase themes
export const phaseThemes: Record<AnimationPhase, PhaseTheme> = {
  idle: {
    colors: {
      primary: colors.primary,
      secondary: colors.secondary,
      accent: colors.accent,
      background: colors.warm,
      text: '#333',
      glow: 'rgba(255, 107, 107, 0.2)',
    },
    particles: particleConfigs.idle || {
      type: 'sparkle',
      behavior: 'float',
      count: 0,
      colors: [],
      size: { min: 0, max: 0 },
      speed: { min: 0, max: 0 },
      lifetime: 0,
      spread: 0,
    },
    animation: animationPresets.idle,
    icon: '✨',
    label: 'Ready',
  },
  connecting: {
    colors: {
      primary: colors.secondary,
      secondary: colors.primary,
      accent: colors.accent,
      background: 'linear-gradient(135deg, #E8FFF9 0%, #FFF9F5 100%)',
      text: '#333',
      glow: 'rgba(78, 205, 196, 0.3)',
    },
    particles: particleConfigs.connecting!,
    animation: animationPresets.connecting,
    icon: '🔗',
    label: 'Connecting',
  },
  thinking: {
    colors: {
      primary: colors.purple,
      secondary: '#A855F7',
      accent: '#E879F9',
      background: 'linear-gradient(135deg, #F5F3FF 0%, #FFF9F5 100%)',
      text: '#333',
      glow: 'rgba(155, 89, 182, 0.3)',
    },
    particles: particleConfigs.thinking!,
    animation: animationPresets.thinking,
    icon: '💭',
    label: 'Thinking',
  },
  tool_executing: {
    colors: {
      primary: colors.yellow,
      secondary: '#FBBF24',
      accent: colors.accent,
      background: 'linear-gradient(135deg, #FFFBEB 0%, #FFF9F5 100%)',
      text: '#333',
      glow: 'rgba(241, 196, 15, 0.4)',
    },
    particles: particleConfigs.tool_executing!,
    animation: animationPresets.tool_executing,
    icon: '⚡',
    label: 'Running Tool',
  },
  revealing: {
    colors: {
      primary: colors.primary,
      secondary: colors.secondary,
      accent: colors.accent,
      background: 'linear-gradient(135deg, #FFE8E8 0%, #E8FFF9 100%)',
      text: '#333',
      glow: 'rgba(255, 107, 107, 0.3)',
    },
    particles: particleConfigs.revealing!,
    animation: animationPresets.revealing,
    icon: '🎁',
    label: 'Revealing',
  },
  complete: {
    colors: {
      primary: colors.green,
      secondary: colors.secondary,
      accent: colors.accent,
      background: 'linear-gradient(135deg, #ECFDF5 0%, #FFF9F5 100%)',
      text: '#333',
      glow: 'rgba(46, 204, 113, 0.3)',
    },
    particles: particleConfigs.complete!,
    animation: animationPresets.complete,
    icon: '🎉',
    label: 'Complete',
  },
  error: {
    colors: {
      primary: colors.red,
      secondary: '#F87171',
      accent: '#FCA5A5',
      background: 'linear-gradient(135deg, #FEF2F2 0%, #FFF9F5 100%)',
      text: '#991B1B',
      glow: 'rgba(231, 76, 60, 0.2)',
    },
    particles: particleConfigs.error!,
    animation: animationPresets.error,
    icon: '❌',
    label: 'Error',
  },
}

// Tool icons mapping
export const toolIcons: Record<string, string> = {
  analyze_drawing: '🔍',
  generate_story: '📝',
  generate_audio: '🎵',
  safety_check: '🛡️',
  memory_recall: '🧠',
  age_adaptation: '👶',
  default: '⚙️',
}

// Get icon for a tool
export function getToolIcon(toolName: string): string {
  const normalizedName = toolName.toLowerCase().replace(/[^a-z_]/g, '')
  return toolIcons[normalizedName] || toolIcons.default
}

// Get phase theme
export function getPhaseTheme(phase: AnimationPhase): PhaseTheme {
  return phaseThemes[phase]
}

// Get animation preset
export function getAnimationPreset(phase: AnimationPhase): AnimationPreset {
  return animationPresets[phase]
}

// Get particle config
export function getParticleConfig(phase: AnimationPhase): ParticleConfig | undefined {
  return particleConfigs[phase]
}

// Stagger children animation config
export const staggerChildren = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
}

// Stagger item animation config
export const staggerItem = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.4, ease: 'easeOut' },
  },
}

// Reveal animation for content
export const revealAnimation = {
  hidden: { opacity: 0, y: 30, scale: 0.9 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.6,
      ease: [0.22, 1, 0.36, 1],
    },
  },
}

// Celebration animation
export const celebrationAnimation = {
  initial: { scale: 0, rotate: -180 },
  animate: {
    scale: 1,
    rotate: 0,
    transition: {
      type: 'spring',
      stiffness: 200,
      damping: 15,
    },
  },
}

// Shake animation for errors
export const shakeAnimation = {
  shake: {
    x: [0, -10, 10, -10, 10, 0],
    transition: { duration: 0.5 },
  },
}

// Pulse animation
export const pulseAnimation = {
  pulse: {
    scale: [1, 1.05, 1],
    opacity: [1, 0.8, 1],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
}

// Float animation
export const floatAnimation = {
  float: {
    y: [0, -10, 0],
    transition: {
      duration: 3,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
}

// Bounce animation
export const bounceAnimation = {
  bounce: {
    y: [0, -20, 0],
    transition: {
      duration: 0.6,
      times: [0, 0.5, 1],
      ease: ['easeOut', 'easeIn'],
    },
  },
}

// Spin animation
export const spinAnimation = {
  spin: {
    rotate: 360,
    transition: {
      duration: 1,
      repeat: Infinity,
      ease: 'linear',
    },
  },
}
