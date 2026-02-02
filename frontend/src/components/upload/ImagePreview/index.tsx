import { motion } from 'framer-motion'
import Button from '@/components/common/Button'

interface ImagePreviewProps {
  src: string
  fileName?: string
  onRemove: () => void
  className?: string
}

function ImagePreview({ src, fileName, onRemove, className = '' }: ImagePreviewProps) {
  return (
    <motion.div
      className={`relative ${className}`}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
    >
      {/* Image container */}
      <div className="relative rounded-card overflow-hidden shadow-card bg-white p-2">
        {/* Decorative border */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-secondary/20 to-accent/20 rounded-card" />

        {/* Image */}
        <div className="relative rounded-lg overflow-hidden">
          <img
            src={src}
            alt="Uploaded artwork"
            className="w-full h-auto max-h-80 object-contain"
          />

          {/* Hover overlay */}
          <motion.div
            className="absolute inset-0 bg-black/0 hover:bg-black/20 transition-colors flex items-center justify-center"
            whileHover={{ opacity: 1 }}
          >
            <motion.span
              className="text-4xl opacity-0 hover:opacity-100 transition-opacity"
              initial={{ scale: 0 }}
              whileHover={{ scale: 1 }}
            >
              🔍
            </motion.span>
          </motion.div>
        </div>
      </div>

      {/* Filename and remove button */}
      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🎨</span>
          <span className="text-gray-600 text-sm truncate max-w-[200px]">
            {fileName || 'My artwork'}
          </span>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          className="text-gray-500 hover:text-red-500"
        >
          <span className="mr-1">🗑️</span>
          Change
        </Button>
      </div>

      {/* Decorative elements */}
      <motion.div
        className="absolute -top-3 -right-3 text-2xl"
        animate={{ rotate: [0, 10, -10, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
      >
        ⭐
      </motion.div>

      <motion.div
        className="absolute -bottom-2 -left-2 text-xl"
        animate={{ scale: [1, 1.1, 1] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      >
        🌟
      </motion.div>
    </motion.div>
  )
}

export default ImagePreview
