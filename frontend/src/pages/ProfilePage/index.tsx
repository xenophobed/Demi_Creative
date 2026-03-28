import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import TiltCard from '@/components/depth/TiltCard'
import useAuthStore from '@/store/useAuthStore'
import useChildStore from '@/store/useChildStore'
import { authService } from '@/api/services/authService'
import type { UpdateProfileRequest } from '@/types/auth'
import AvatarDisplay from '@/components/common/AvatarDisplay'
import CharacterGallery from './CharacterGallery'
import PreferenceSummary from './PreferenceSummary'
import { useMemoryApi } from '@/hooks/useMemoryApi'

const ANIMAL_EMOJIS = [
  '🐶', '🐱', '🐼', '🐨', '🦊', '🐰', '🐸', '🦁',
  '🐯', '🐮', '🐷', '🐵', '🐔', '🐧', '🦄', '🐲',
  '🐢', '🦋', '🐬', '🐙',
]

function ProfilePage() {
  const navigate = useNavigate()
  const { isAuthenticated, user, setUser } = useAuthStore()
  const { currentChild } = useChildStore()
  const childId = currentChild?.child_id || null
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState<UpdateProfileRequest>({
    display_name: user?.display_name || '',
    avatar_url: user?.avatar_url || '',
  })
  const [saving, setSaving] = useState(false)
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [clearSuccess, setClearSuccess] = useState(false)
  const [clearError, setClearError] = useState<string | null>(null)

  const {
    characters,
    preferences,
    isLoading: memoryLoading,
    deletePreferences,
    isDeleting,
  } = useMemoryApi(isAuthenticated ? childId : null)

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login')
    }
  }, [isAuthenticated, navigate])

  // Fetch user stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['user-stats'],
    queryFn: () => authService.getUserStats(),
    enabled: isAuthenticated,
  })

  const handleSaveProfile = async () => {
    setSaving(true)
    try {
      const updated = await authService.updateProfile(editForm)
      setUser(updated)
      setIsEditing(false)
    } catch (err) {
      console.error('Failed to update profile:', err)
    } finally {
      setSaving(false)
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const handleClearMemory = async () => {
    setClearError(null)
    try {
      await deletePreferences()
      setShowClearConfirm(false)
      setClearSuccess(true)
      setTimeout(() => setClearSuccess(false), 3000)
    } catch (err) {
      console.error('Failed to clear memory:', err)
      setClearError('Failed to clear memory. Please try again.')
    }
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className="space-y-6">
      {/* Profile Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card className="p-6">
          <div className="flex flex-col items-center text-center sm:flex-row sm:items-center sm:text-left gap-4">
            <AvatarDisplay avatarUrl={user?.avatar_url} size="lg" />
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-bold text-gray-800 truncate">
                {user?.display_name || user?.username}
              </h1>
              <p className="text-gray-500 text-sm">@{user?.username}</p>
              <p className="text-gray-400 text-xs">{user?.email}</p>
              {user?.created_at && (
                <p className="text-gray-400 text-xs mt-1">
                  Member since {formatDate(user.created_at)}
                </p>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full sm:w-auto"
              onClick={() => {
                setEditForm({
                  display_name: user?.display_name || '',
                  avatar_url: user?.avatar_url || '',
                })
                setIsEditing(!isEditing)
              }}
            >
              {isEditing ? 'Cancel' : 'Edit Profile'}
            </Button>
          </div>

          {/* Inline Edit Form */}
          {isEditing && (
            <motion.div
              className="mt-4 pt-4 border-t border-gray-100 space-y-3"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
            >
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">
                  Display Name
                </label>
                <input
                  type="text"
                  value={editForm.display_name || ''}
                  onChange={(e) =>
                    setEditForm({ ...editForm, display_name: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  placeholder="Your display name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-2">
                  Choose Your Avatar
                </label>
                <div className="flex items-center gap-3 mb-3">
                  <AvatarDisplay avatarUrl={editForm.avatar_url || undefined} size="md" />
                  <span className="text-sm text-gray-500">
                    {editForm.avatar_url?.startsWith('emoji:')
                      ? 'Tap an animal to change'
                      : 'Pick your favorite animal!'}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {ANIMAL_EMOJIS.map((emoji) => {
                    const emojiValue = `emoji:${emoji}`
                    const isSelected = editForm.avatar_url === emojiValue
                    return (
                      <motion.button
                        key={emoji}
                        type="button"
                        className={`w-10 h-10 rounded-lg text-xl flex items-center justify-center transition-all ${
                          isSelected
                            ? 'border-2 border-primary bg-primary/10 shadow-md'
                            : 'border border-gray-200 hover:border-gray-300 hover:shadow-sm'
                        }`}
                        onClick={() =>
                          setEditForm({ ...editForm, avatar_url: emojiValue })
                        }
                        whileHover={{ scale: 1.15, y: -2 }}
                        whileTap={{ scale: 0.9 }}
                      >
                        {emoji}
                      </motion.button>
                    )
                  })}
                </div>
              </div>
              <Button
                size="sm"
                onClick={handleSaveProfile}
                isLoading={saving}
              >
                Save Changes
              </Button>
            </motion.div>
          )}
        </Card>
      </motion.div>

      {/* Stats Cards */}
      <motion.div
        className="grid grid-cols-3 gap-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <TiltCard maxTilt={10} glare className="cursor-pointer" onClick={() => navigate('/library?tab=art-stories')}>
          <div className="bg-gradient-to-br from-primary/10 to-primary/5 rounded-card p-5 text-center">
            <div className="text-4xl mb-2">🎨</div>
            <div className="text-3xl font-bold text-gray-800">
              {statsLoading ? '...' : stats?.art_story_count ?? 0}
            </div>
            <div className="text-sm text-gray-500 mt-1">Art Stories</div>
          </div>
        </TiltCard>
        <TiltCard maxTilt={10} glare className="cursor-pointer" onClick={() => navigate('/library?tab=interactive')}>
          <div className="bg-gradient-to-br from-accent/20 to-accent/10 rounded-card p-5 text-center">
            <div className="text-4xl mb-2">🎭</div>
            <div className="text-3xl font-bold text-gray-800">
              {statsLoading ? '...' : stats?.interactive_count ?? 0}
            </div>
            <div className="text-sm text-gray-500 mt-1">Interactive Tales</div>
          </div>
        </TiltCard>
        <TiltCard maxTilt={10} glare className="cursor-pointer" onClick={() => navigate('/library?tab=kids-news')}>
          <div className="bg-gradient-to-br from-secondary/20 to-secondary/10 rounded-card p-5 text-center">
            <div className="text-4xl mb-2">📰</div>
            <div className="text-3xl font-bold text-gray-800">
              {statsLoading ? '...' : stats?.news_count ?? 0}
            </div>
            <div className="text-sm text-gray-500 mt-1">Kids News</div>
          </div>
        </TiltCard>
      </motion.div>

      {/* Morning Show settings shortcut */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <Card className="p-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-gray-800">Morning Show Preferences</h2>
            <p className="text-sm text-gray-500">Manage topic channels for Daily Drop episodes.</p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate('/morning-show/subscriptions')}
          >
            Manage Channels
          </Button>
        </Card>
      </motion.section>

      {/* Character Gallery */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <CharacterGallery characters={characters} isLoading={memoryLoading} />
      </motion.section>

      {/* Preference Summary */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <PreferenceSummary preferences={preferences} isLoading={memoryLoading} />
      </motion.section>

      {/* Privacy / Clear Memory */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card className="p-4">
          <h2 className="text-base font-bold text-gray-800 mb-1">Privacy</h2>
          <p className="text-sm text-gray-500 mb-3">
            Clear all saved characters, themes, and preference data.
          </p>

          {clearSuccess && (
            <div className="mb-3 rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-700">
              Memory cleared successfully.
            </div>
          )}

          {!showClearConfirm ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowClearConfirm(true)}
            >
              Clear Memory
            </Button>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm text-red-600 font-medium">
                Are you sure? This cannot be undone.
              </p>
              {clearError && (
                <p className="text-sm text-red-500 w-full">{clearError}</p>
              )}
              <Button
                size="sm"
                variant="primary"
                className="bg-red-500 hover:bg-red-600"
                onClick={handleClearMemory}
                isLoading={isDeleting}
              >
                Yes, Clear
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => { setShowClearConfirm(false); setClearError(null) }}
              >
                Cancel
              </Button>
            </div>
          )}
        </Card>
      </motion.section>
    </div>
  )
}

export default ProfilePage
