import { motion } from 'framer-motion'
import { useState } from 'react'
import type { StoryChoice } from '@/types/api'

interface ChoiceButtonsProps {
  choices: StoryChoice[]
  onChoose: (choiceId: string) => void
  isLoading: boolean
  disabled: boolean
  className?: string
}

function ChoiceButtons({
  choices,
  onChoose,
  isLoading,
  disabled,
  className = '',
}: ChoiceButtonsProps) {
  return (
    <div
      className={`flex flex-col md:flex-row gap-3 ${className}`}
    >
      {choices.map((choice, index) => (
        <ChoiceButton
          key={choice.choice_id}
          choice={choice}
          index={index}
          onChoose={onChoose}
          isLoading={isLoading}
          disabled={disabled}
        />
      ))}
    </div>
  )
}

interface ChoiceButtonProps {
  choice: StoryChoice
  index: number
  onChoose: (choiceId: string) => void
  isLoading: boolean
  disabled: boolean
}

function ChoiceButton({ choice, index, onChoose, isLoading, disabled }: ChoiceButtonProps) {
  const [isHovered, setIsHovered] = useState(false)

  const handleMouseEnter = () => {
    if (disabled || isLoading) return
    setIsHovered(true)
  }

  const handleMouseLeave = () => {
    setIsHovered(false)
  }

  const interactive = !disabled && !isLoading

  return (
    <motion.button
      className={`
        flex-1 flex items-center gap-3
        px-5 py-4 rounded-xl
        bg-gradient-to-br from-white to-gray-50
        border-2 border-gray-200
        text-left font-medium text-gray-700
        transition-colors duration-200
        ${
          disabled || isLoading
            ? 'opacity-50 cursor-not-allowed'
            : 'hover:border-primary cursor-pointer'
        }
      `}
      onClick={() => interactive && onChoose(choice.choice_id)}
      disabled={disabled || isLoading}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      style={{
        boxShadow: isHovered ? '0 10px 22px rgba(0,0,0,0.10)' : '0 4px 12px rgba(0,0,0,0.05)',
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      whileHover={interactive ? { y: -3, scale: 1.02 } : undefined}
      whileTap={interactive ? { scale: 0.98 } : undefined}
    >
          {/* Emoji */}
          <motion.span
            className="text-3xl flex-shrink-0"
            animate={
              !disabled && !isLoading
                ? { rotate: [0, -5, 5, 0] }
                : {}
            }
            transition={{
              duration: 2,
              repeat: Infinity,
              delay: index * 0.3,
            }}
          >
            {choice.emoji}
          </motion.span>

          {/* Text */}
          <span className="flex-1">{choice.text}</span>

        {/* Glare effect */}
        {isHovered && (
          <motion.div
            className="absolute inset-0 rounded-xl pointer-events-none overflow-hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.15 }}
          >
            <div
              className="absolute inset-0"
              style={{
                background: 'linear-gradient(135deg, rgba(255,255,255,0.4) 0%, transparent 50%)',
              }}
            />
          </motion.div>
        )}

        {/* Loading indicator for this specific button */}
        {isLoading && (
          <LoadingSpinner />
        )}
      </motion.button>
  )
}

function LoadingSpinner() {
  return (
    <svg
      className="animate-spin h-5 w-5 text-primary flex-shrink-0"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
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
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}

export default ChoiceButtons
