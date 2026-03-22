import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import TiltCard from '@/components/depth/TiltCard'
import useAuthStore from '@/store/useAuthStore'
import { authService } from '@/api/services/authService'
import type { UpdateProfileRequest } from '@/types/auth'
import { resolveMediaUrl } from '@/utils/mediaUrl'

function ProfilePage() {
  const navigate = useNavigate()
  const { isAuthenticated, user, setUser } = useAuthStore()
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState<UpdateProfileRequest>({
    display_name: user?.display_name || '',
    avatar_url: user?.avatar_url || '',
  })
  const [saving, setSaving] = useState(false)

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
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center text-3xl overflow-hidden flex-shrink-0">
              {user?.avatar_url ? (
                <img
                  src={resolveMediaUrl(user.avatar_url) || user.avatar_url}
                  alt="avatar"
                  className="w-full h-full object-cover"
                />
              ) : (
                '👤'
              )}
            </div>
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
                <label className="block text-sm font-medium text-gray-600 mb-1">
                  Avatar URL
                </label>
                <input
                  type="text"
                  value={editForm.avatar_url || ''}
                  onChange={(e) =>
                    setEditForm({ ...editForm, avatar_url: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  placeholder="https://example.com/avatar.png"
                />
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
    </div>
  )
}

export default ProfilePage
