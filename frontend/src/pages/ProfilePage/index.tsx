import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import TiltCard from '@/components/depth/TiltCard'
import useAuthStore from '@/store/useAuthStore'
import { authService } from '@/api/services/authService'
import type { UpdateProfileRequest } from '@/types/auth'

function ProfilePage() {
  const navigate = useNavigate()
  const { isAuthenticated, user, setUser } = useAuthStore()
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState<UpdateProfileRequest>({
    display_name: user?.display_name || '',
    avatar_url: user?.avatar_url || '',
  })
  const [saving, setSaving] = useState(false)

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    navigate('/login')
    return null
  }

  // Fetch user stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['user-stats'],
    queryFn: () => authService.getUserStats(),
    enabled: isAuthenticated,
  })

  // Fetch recent stories
  const { data: storiesData, isLoading: storiesLoading } = useQuery({
    queryKey: ['my-stories'],
    queryFn: () => authService.getMyStories({ limit: 5 }),
    enabled: isAuthenticated,
  })

  // Fetch recent sessions
  const { data: sessionsData, isLoading: sessionsLoading } = useQuery({
    queryKey: ['my-sessions'],
    queryFn: () => authService.getMySessions({ limit: 5 }),
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

  return (
    <div className="space-y-6">
      {/* Profile Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card className="p-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center text-3xl overflow-hidden flex-shrink-0">
              {user?.avatar_url ? (
                <img
                  src={user.avatar_url}
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
        className="grid grid-cols-2 gap-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <TiltCard maxTilt={10} glare className="cursor-default">
          <div className="bg-gradient-to-br from-primary/10 to-primary/5 rounded-card p-5 text-center">
            <div className="text-4xl mb-2">📖</div>
            <div className="text-3xl font-bold text-gray-800">
              {statsLoading ? '...' : stats?.story_count ?? 0}
            </div>
            <div className="text-sm text-gray-500 mt-1">Stories Created</div>
          </div>
        </TiltCard>
        <TiltCard maxTilt={10} glare className="cursor-default">
          <div className="bg-gradient-to-br from-accent/20 to-accent/10 rounded-card p-5 text-center">
            <div className="text-4xl mb-2">🎭</div>
            <div className="text-3xl font-bold text-gray-800">
              {statsLoading ? '...' : stats?.session_count ?? 0}
            </div>
            <div className="text-sm text-gray-500 mt-1">Interactive Sessions</div>
          </div>
        </TiltCard>
      </motion.div>

      {/* Recent Stories */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h2 className="text-lg font-bold text-gray-800 mb-3 flex items-center gap-2">
          <span>📚</span> Recent Stories
        </h2>
        {storiesLoading ? (
          <p className="text-gray-400 text-sm">Loading stories...</p>
        ) : storiesData?.stories && storiesData.stories.length > 0 ? (
          <div className="space-y-2">
            {storiesData.stories.map((story) => (
              <Card
                key={story.story_id}
                className="p-3 cursor-pointer"
                onClick={() => navigate(`/story/${story.story_id}`)}
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary/20 to-secondary/10 flex items-center justify-center overflow-hidden flex-shrink-0">
                    {story.image_url ? (
                      <img
                        src={story.image_url.startsWith('/') ? story.image_url : '/' + story.image_url}
                        alt="Artwork"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="text-lg">📖</span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-700 truncate">
                      {story.story_preview || `Story #${story.story_id.slice(0, 8)}`}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
                      <span>{story.word_count} words</span>
                      <span>{formatDate(story.created_at)}</span>
                    </div>
                  </div>
                  {story.themes && story.themes.length > 0 && (
                    <div className="flex gap-1 flex-shrink-0">
                      {story.themes.slice(0, 2).map((theme) => (
                        <span
                          key={theme}
                          className="text-xs px-1.5 py-0.5 bg-primary/10 text-primary rounded-full"
                        >
                          {theme}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-gray-400 text-sm">No stories yet. Start creating!</p>
        )}
      </motion.section>

      {/* Recent Sessions */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <h2 className="text-lg font-bold text-gray-800 mb-3 flex items-center gap-2">
          <span>🎭</span> Recent Sessions
        </h2>
        {sessionsLoading ? (
          <p className="text-gray-400 text-sm">Loading sessions...</p>
        ) : sessionsData?.sessions && sessionsData.sessions.length > 0 ? (
          <div className="space-y-2">
            {sessionsData.sessions.map((session) => (
              <Card key={session.session_id} className="p-3">
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-700 truncate">
                      {session.story_title}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
                      <span
                        className={`px-1.5 py-0.5 rounded-full text-xs font-medium ${
                          session.status === 'active'
                            ? 'bg-green-100 text-green-700'
                            : session.status === 'completed'
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {session.status}
                      </span>
                      <span>{formatDate(session.created_at)}</span>
                    </div>
                  </div>
                  {/* Progress bar */}
                  <div className="w-20 flex-shrink-0">
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-primary to-secondary rounded-full transition-all"
                        style={{
                          width: `${
                            session.total_segments > 0
                              ? (session.current_segment / session.total_segments) * 100
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                    <p className="text-xs text-gray-400 text-center mt-0.5">
                      {session.current_segment}/{session.total_segments}
                    </p>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-gray-400 text-sm">No interactive sessions yet.</p>
        )}
      </motion.section>
    </div>
  )
}

export default ProfilePage
