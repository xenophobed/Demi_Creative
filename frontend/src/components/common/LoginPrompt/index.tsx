import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'

interface LoginPromptProps {
  feature: string
}

function LoginPrompt({ feature }: LoginPromptProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', damping: 25, stiffness: 300 }}
    >
      <Card>
        <div className="text-center py-8">
          <span className="text-6xl block mb-4">🔒</span>
          <h2 className="text-xl font-bold text-gray-800 mb-2">
            Log in to {feature}
          </h2>
          <p className="text-gray-500 mb-6 max-w-sm mx-auto">
            Create a free account to start making amazing stories, explore news, and save your creations!
          </p>
          <Link to="/login">
            <Button size="lg" leftIcon={<span>🚀</span>}>
              Log In or Sign Up
            </Button>
          </Link>
        </div>
      </Card>
    </motion.div>
  )
}

export default LoginPrompt
