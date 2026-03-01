import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import useStoryStore from '@/store/useStoryStore'
import useAuthStore from '@/store/useAuthStore'
import useChildStore from '@/store/useChildStore'
import { authService } from '@/api/services/authService'
import { storyService } from '@/api/services/storyService'
import SafetyBadge from '@/components/story/SafetyBadge'
import type { UserStorySummary, UserSessionSummary } from '@/types/auth'
import type { NewsToKidsResponse } from '@/types/api'

// Content type tabs
type ContentTab = 'all' | 'art-stories' | 'interactive' | 'news'

const TABS: { id: ContentTab; label: string; icon: string }[] = [
  { id: 'all', label: 'All', icon: '📚' },
  { id: 'art-stories', label: 'Art Stories', icon: '🎨' },
  { id: 'interactive', label: 'Interactive', icon: '🌿' },
  { id: 'news', label: 'News', icon: '📰' },
]

// ---- unified library item type ----

type LibraryItemType = 'art-story' | 'interactive' | 'news'

interface LibraryItem {
  id: string
  type: LibraryItemType
  title: string
  preview: string
  image_url: string | null
  audio_url: string | null
  created_at: string
  // Art stories
  safety_score?: number
  word_count?: number
  themes?: string[]
  // Interactive sessions
  progress?: number          // 0-100
  status?: string
  // News items
  category?: string
}

// ---- helpers ----

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function sessionProgress(session: UserSessionSummary): number {
  if (!session.total_segments || session.total_segments === 0) return 0
  return Math.round((session.current_segment / session.total_segments) * 100)
}

function truncatePreview(text: string, maxLen = 120): string {
  if (!text) return ''
  return text.length > maxLen ? `${text.slice(0, maxLen)}...` : text
}

// ---- subcomponents ----

function DeleteButton({ onDelete }: { onDelete: () => void }) {
  return (
    <motion.button
      className="flex-shrink-0 p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
      onClick={(e) => {
        e.stopPropagation()
        onDelete()
      }}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      title="Delete"
    >
      <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
    </motion.button>
  )
}

function ArtStoryCard({ item, onClick, onDelete }: { item: LibraryItem; onClick: () => void; onDelete: () => void }) {
  // Use state for image error to avoid direct DOM mutation via parentElement!.innerHTML
  const [imgError, setImgError] = useState(false)

  return (
    <Card className="cursor-pointer" onClick={onClick}>
      <div className="flex gap-4">
        {/* Thumbnail */}
        <div className="flex-shrink-0 w-20 h-20 rounded-lg bg-gradient-to-br from-primary/20 via-secondary/10 to-accent/20 flex items-center justify-center overflow-hidden">
          {item.image_url && !imgError ? (
            <img
              src={item.image_url.startsWith('/') ? item.image_url : '/' + item.image_url}
              alt="Artwork"
              className="w-full h-full object-cover"
              onError={() => setImgError(true)}
            />
          ) : (
            <motion.span
              className="text-4xl"
              whileHover={{ rotate: [0, -10, 10, 0] }}
              transition={{ duration: 0.5 }}
            >
              📖
            </motion.span>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <span className="text-xs font-medium px-2 py-0.5 bg-primary/10 text-primary rounded-full mb-1 inline-block">
                Art Story
              </span>
              <h3 className="font-bold text-gray-800 truncate">
                {item.title}
              </h3>
            </div>
            {item.safety_score !== undefined && (
              <SafetyBadge score={item.safety_score} />
            )}
          </div>

          <p className="text-gray-500 text-sm mt-1 line-clamp-2">
            {truncatePreview(item.preview)}
          </p>

          <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
            {item.word_count !== undefined && (
              <span className="flex items-center gap-1">
                <span>📝</span>
                {item.word_count} words
              </span>
            )}
            <span className="flex items-center gap-1">
              <span>🕐</span>
              {formatDate(item.created_at)}
            </span>
            {item.audio_url && (
              <span className="flex items-center gap-1 text-secondary">
                <span>🔊</span>
                Audio
              </span>
            )}
          </div>

          {item.themes && item.themes.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {item.themes.slice(0, 3).map((theme) => (
                <span
                  key={theme}
                  className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded-full"
                >
                  {theme}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex-shrink-0 flex flex-col items-center justify-between py-1">
          <DeleteButton onDelete={onDelete} />
          <motion.span
            className="text-gray-400"
            animate={{ x: [0, 4, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            →
          </motion.span>
        </div>
      </div>
    </Card>
  )
}

function InteractiveStoryCard({ item, onClick, onDelete }: { item: LibraryItem; onClick: () => void; onDelete: () => void }) {
  const progress = item.progress ?? 0

  return (
    <Card className="cursor-pointer" onClick={onClick}>
      <div className="flex gap-4">
        {/* Icon */}
        <div className="flex-shrink-0 w-20 h-20 rounded-lg bg-gradient-to-br from-secondary/20 via-accent/10 to-primary/20 flex items-center justify-center">
          <motion.span
            className="text-4xl"
            whileHover={{ scale: 1.1 }}
            transition={{ duration: 0.3 }}
          >
            🌿
          </motion.span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <span className="text-xs font-medium px-2 py-0.5 bg-secondary/10 text-secondary rounded-full mb-1 inline-block">
                Interactive Story
              </span>
              <h3 className="font-bold text-gray-800 truncate">{item.title}</h3>
            </div>
            {item.status && (
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  item.status === 'completed'
                    ? 'bg-green-100 text-green-700'
                    : item.status === 'expired'
                    ? 'bg-gray-100 text-gray-500'
                    : 'bg-blue-100 text-blue-700'
                }`}
              >
                {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
              </span>
            )}
          </div>

          {/* Progress bar */}
          <div className="mt-2">
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>Progress</span>
              <span>{progress}%</span>
            </div>
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-secondary rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
              />
            </div>
          </div>

          <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <span>🕐</span>
              {formatDate(item.created_at)}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex-shrink-0 flex flex-col items-center justify-between py-1">
          <DeleteButton onDelete={onDelete} />
          <motion.span
            className="text-gray-400"
            animate={{ x: [0, 4, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            →
          </motion.span>
        </div>
      </div>
    </Card>
  )
}

function NewsCard({ item, onDelete }: { item: LibraryItem; onDelete: () => void }) {
  return (
    <Card>
      <div className="flex gap-4">
        {/* Icon */}
        <div className="flex-shrink-0 w-20 h-20 rounded-lg bg-gradient-to-br from-accent/20 via-primary/10 to-secondary/20 flex items-center justify-center">
          <motion.span
            className="text-4xl"
            whileHover={{ rotate: [0, -5, 5, 0] }}
            transition={{ duration: 0.5 }}
          >
            📰
          </motion.span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div>
            <span className="text-xs font-medium px-2 py-0.5 bg-accent/10 text-accent rounded-full mb-1 inline-block">
              {item.category
                ? item.category.charAt(0).toUpperCase() + item.category.slice(1)
                : 'News'}
            </span>
            <h3 className="font-bold text-gray-800 truncate">{item.title}</h3>
          </div>

          <p className="text-gray-500 text-sm mt-1 line-clamp-2">
            {truncatePreview(item.preview)}
          </p>

          <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <span>🕐</span>
              {formatDate(item.created_at)}
            </span>
            {item.audio_url && (
              <span className="flex items-center gap-1 text-secondary">
                <span>🔊</span>
                Audio
              </span>
            )}
          </div>
        </div>

        {/* Delete */}
        <div className="flex-shrink-0 flex items-center">
          <DeleteButton onDelete={onDelete} />
        </div>
      </div>
    </Card>
  )
}

// ---- main page ----

function LibraryPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { storyHistory, clearHistory, setCurrentStory, removeStory } = useStoryStore()
  const { isAuthenticated } = useAuthStore()
  const { currentChild, defaultChildId } = useChildStore()

  const [activeTab, setActiveTab] = useState<ContentTab>('all')
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const [pageSize] = useState(20)
  const [artOffset, setArtOffset] = useState(0)
  // Accumulate art story pages so "Load More" appends rather than replaces
  const [accumulatedServerArt, setAccumulatedServerArt] = useState<UserStorySummary[]>([])

  const childId = currentChild?.child_id || defaultChildId

  // ---- data fetching ----

  // Art stories (authenticated) — fetches one page at a time
  const { data: serverArtData, isLoading: artLoading } = useQuery({
    queryKey: ['library-art-stories', artOffset, pageSize],
    queryFn: () => authService.getMyStories({ limit: pageSize, offset: artOffset }),
    enabled: isAuthenticated,
  })

  // Append newly fetched page into the accumulator so prior pages are preserved
  useEffect(() => {
    if (serverArtData?.stories && serverArtData.stories.length > 0) {
      setAccumulatedServerArt((prev) => {
        const existingIds = new Set(prev.map((s) => s.story_id))
        const newItems = serverArtData.stories.filter((s) => !existingIds.has(s.story_id))
        return newItems.length > 0 ? [...prev, ...newItems] : prev
      })
    }
  }, [serverArtData])

  // Art stories by child_id (unauthenticated)
  const { data: childArtStories } = useQuery({
    queryKey: ['library-child-art-stories', childId],
    queryFn: () => storyService.getStoryHistory(childId),
    enabled: !!childId && !isAuthenticated,
  })

  // Interactive sessions (authenticated)
  const { data: sessionData, isLoading: sessionsLoading } = useQuery({
    queryKey: ['library-sessions'],
    queryFn: () => authService.getMySessions({ limit: 50, offset: 0 }),
    enabled: isAuthenticated,
  })

  // News history by child_id
  const { data: newsHistory, isLoading: newsLoading } = useQuery({
    queryKey: ['library-news-history', childId],
    queryFn: () => storyService.getNewsHistory(childId),
    enabled: !!childId,
  })

  // ---- build unified art story items ----

  const artItems: LibraryItem[] = (() => {
    if (isAuthenticated && accumulatedServerArt.length > 0) {
      const serverIds = new Set(accumulatedServerArt.map((s) => s.story_id))

      // UserStorySummary does not include safety_score; SafetyBadge will not render
      // for server-side items until the API is extended to return it.
      const serverItems: LibraryItem[] = accumulatedServerArt.map((s) => ({
        id: s.story_id,
        type: 'art-story',
        title: `Story #${s.story_id.slice(0, 8)}`,
        preview: s.story_preview || '',
        image_url: s.image_url,
        audio_url: s.audio_url,
        created_at: s.created_at,
        word_count: s.word_count,
        themes: s.themes,
      }))

      const localOnly: LibraryItem[] = storyHistory
        .filter((s) => !serverIds.has(s.story_id))
        .map((s) => ({
          id: s.story_id,
          type: 'art-story',
          title: `Story #${s.story_id.slice(0, 8)}`,
          preview: s.story.text,
          image_url: s.image_url ?? null,
          audio_url: s.audio_url ?? null,
          created_at: s.created_at,
          safety_score: s.safety_score as number | undefined,
          word_count: s.story.word_count,
          themes: s.educational_value.themes,
        }))

      return [...serverItems, ...localOnly]
    }

    if (childArtStories && childArtStories.length > 0) {
      const serverIds = new Set(childArtStories.map((s) => s.story_id))

      const serverItems: LibraryItem[] = childArtStories.map((s) => ({
        id: s.story_id,
        type: 'art-story',
        title: `Story #${s.story_id.slice(0, 8)}`,
        preview: s.story?.text ? s.story.text.slice(0, 200) : '',
        image_url: s.image_url ?? null,
        audio_url: s.audio_url ?? null,
        created_at: s.created_at,
        safety_score: s.safety_score as number | undefined,
        word_count: s.story?.word_count || 0,
        themes: s.educational_value?.themes || [],
      }))

      const localOnly: LibraryItem[] = storyHistory
        .filter((s) => !serverIds.has(s.story_id))
        .map((s) => ({
          id: s.story_id,
          type: 'art-story',
          title: `Story #${s.story_id.slice(0, 8)}`,
          preview: s.story.text,
          image_url: s.image_url ?? null,
          audio_url: s.audio_url ?? null,
          created_at: s.created_at,
          safety_score: s.safety_score as number | undefined,
          word_count: s.story.word_count,
          themes: s.educational_value.themes,
        }))

      return [...serverItems, ...localOnly]
    }

    return storyHistory.map((s) => ({
      id: s.story_id,
      type: 'art-story',
      title: `Story #${s.story_id.slice(0, 8)}`,
      preview: s.story.text,
      image_url: s.image_url ?? null,
      audio_url: s.audio_url ?? null,
      created_at: s.created_at,
      safety_score: s.safety_score,
      word_count: s.story.word_count,
      themes: s.educational_value.themes,
    }))
  })()

  // ---- build interactive session items ----

  const interactiveItems: LibraryItem[] = (sessionData?.sessions ?? []).map(
    (session: UserSessionSummary) => ({
      id: session.session_id,
      type: 'interactive',
      title: session.story_title,
      preview: session.theme ? `Theme: ${session.theme}` : 'Interactive adventure',
      image_url: null,
      audio_url: null,
      created_at: session.created_at,
      progress: sessionProgress(session),
      status: session.status,
    })
  )

  // ---- build news items ----

  const newsItems: LibraryItem[] = (newsHistory ?? []).map((n: NewsToKidsResponse) => ({
    id: n.conversion_id,
    type: 'news',
    title: n.kid_title,
    preview: n.kid_content,
    image_url: null,
    audio_url: n.audio_url,
    created_at: n.created_at,
    category: n.category,
  }))

  // ---- merge + filter ----

  const dateSorter = (a: LibraryItem, b: LibraryItem) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()

  const allItems = [...artItems, ...interactiveItems, ...newsItems].sort(dateSorter)

  // Use .slice() before sorting to avoid mutating the source arrays in-place
  // Filter out items currently being deleted for optimistic UI
  const filterDeleting = (items: LibraryItem[]) =>
    items.filter((i) => !deletingIds.has(i.id))

  const visibleItems = filterDeleting(
    activeTab === 'all'
      ? allItems
      : activeTab === 'art-stories'
      ? artItems.slice().sort(dateSorter)
      : activeTab === 'interactive'
      ? interactiveItems.slice().sort(dateSorter)
      : newsItems.slice().sort(dateSorter)
  )

  const hasMoreArt =
    isAuthenticated && serverArtData && artOffset + pageSize < serverArtData.total

  const isLoading = artLoading || sessionsLoading || newsLoading

  // ---- handlers ----

  const handleItemClick = (item: LibraryItem) => {
    if (item.type === 'art-story') {
      const localStory = storyHistory.find((s) => s.story_id === item.id)
      setCurrentStory(localStory ?? null)
      navigate(`/story/${item.id}`)
    } else if (item.type === 'interactive') {
      navigate(`/interactive?session=${item.id}`)
    }
    // News items are read-only in the library for now
  }

  const handleClearHistory = () => {
    if (
      window.confirm(
        'Are you sure you want to clear all local story history? This cannot be undone.'
      )
    ) {
      // Clears only the local Zustand store; server-side data is unaffected
      clearHistory()
    }
  }

  const handleDeleteItem = async (item: LibraryItem) => {
    const label =
      item.type === 'art-story' ? 'art story' :
      item.type === 'interactive' ? 'interactive story' : 'news article'

    if (!window.confirm(`Delete this ${label}? This cannot be undone.`)) return

    setDeletingIds((prev) => new Set(prev).add(item.id))

    try {
      if (item.type === 'interactive') {
        await storyService.deleteSession(item.id)
        queryClient.invalidateQueries({ queryKey: ['library-sessions'] })
      } else {
        await storyService.deleteStory(item.id)
        // Remove from local store too
        removeStory(item.id)
        // Remove from accumulated server art
        setAccumulatedServerArt((prev) => prev.filter((s) => s.story_id !== item.id))
        queryClient.invalidateQueries({ queryKey: ['library-art-stories'] })
        queryClient.invalidateQueries({ queryKey: ['library-child-art-stories'] })
        queryClient.invalidateQueries({ queryKey: ['library-news-history'] })
      }
    } catch {
      // Deletion failed — remove from deleting set to restore the card
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev)
        next.delete(item.id)
        return next
      })
    }
  }

  const handleLoadMoreArt = () => {
    setArtOffset((prev) => prev + pageSize)
  }

  // ---- render ----

  return (
    <div className="space-y-6">
      {/* Page header */}
      <motion.div
        className="flex items-center justify-between"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <span className="text-3xl">📚</span>
          My Library
        </h1>
        {storyHistory.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClearHistory}
            className="text-gray-500"
          >
            Clear Local History
          </Button>
        )}
      </motion.div>

      {/* Tab bar */}
      <motion.div
        className="flex gap-2 overflow-x-auto pb-1"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        {TABS.map((tab) => {
          const count =
            tab.id === 'all'
              ? allItems.length
              : tab.id === 'art-stories'
              ? artItems.length
              : tab.id === 'interactive'
              ? interactiveItems.length
              : newsItems.length

          return (
            <motion.button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-btn font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? 'bg-primary text-white shadow-button'
                  : 'text-gray-600 bg-white/70 hover:bg-gray-100'
              }`}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
              {count > 0 && (
                <span
                  className={`text-xs px-1.5 py-0.5 rounded-full ${
                    activeTab === tab.id
                      ? 'bg-white/30 text-white'
                      : 'bg-gray-200 text-gray-600'
                  }`}
                >
                  {count}
                </span>
              )}
            </motion.button>
          )
        })}
      </motion.div>

      {/* Loading indicator */}
      {isAuthenticated && isLoading && allItems.length === 0 && (
        <motion.div
          className="text-center py-4 text-gray-400 text-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          Loading your library from the server...
        </motion.div>
      )}

      {/* Content list */}
      <AnimatePresence mode="popLayout">
        {visibleItems.length > 0 ? (
          <motion.div className="space-y-4">
            {visibleItems.map((item, index) => (
              <motion.div
                key={`${item.type}-${item.id}`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -100 }}
                transition={{ delay: Math.min(index * 0.04, 0.3) }}
              >
                {item.type === 'art-story' && (
                  <ArtStoryCard item={item} onClick={() => handleItemClick(item)} onDelete={() => handleDeleteItem(item)} />
                )}
                {item.type === 'interactive' && (
                  <InteractiveStoryCard item={item} onClick={() => handleItemClick(item)} onDelete={() => handleDeleteItem(item)} />
                )}
                {item.type === 'news' && <NewsCard item={item} onDelete={() => handleDeleteItem(item)} />}
              </motion.div>
            ))}

            {/* Load more (art stories only, when on All or Art tab) */}
            {hasMoreArt && (activeTab === 'all' || activeTab === 'art-stories') && (
              <motion.div
                className="text-center pt-2"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLoadMoreArt}
                  isLoading={artLoading && artOffset > 0}
                >
                  Load More
                </Button>
              </motion.div>
            )}
          </motion.div>
        ) : (
          // Empty state
          <motion.div
            className="text-center py-16"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <motion.div
              className="text-8xl mb-6"
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              📭
            </motion.div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">
              {activeTab === 'all'
                ? 'Nothing here yet'
                : activeTab === 'art-stories'
                ? 'No art stories yet'
                : activeTab === 'interactive'
                ? 'No interactive stories yet'
                : 'No news conversions yet'}
            </h2>
            <p className="text-gray-500 mb-6">
              {activeTab === 'news'
                ? 'Visit the News Explorer to convert articles for kids!'
                : activeTab === 'interactive'
                ? 'Try the Interactive Story mode to create branching adventures!'
                : 'Upload your first artwork and start creating amazing stories!'}
            </p>
            <Link to={activeTab === 'news' ? '/news' : activeTab === 'interactive' ? '/interactive' : '/upload'}>
              <Button size="lg" leftIcon={<span>✨</span>}>
                {activeTab === 'news'
                  ? 'Go to News Explorer'
                  : activeTab === 'interactive'
                  ? 'Start an Adventure'
                  : 'Start Creating'}
              </Button>
            </Link>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Footer statistics */}
      {allItems.length > 0 && (
        <motion.div
          className="text-center py-4 text-gray-500"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <p>
            Total:{' '}
            <span className="font-bold text-primary">{allItems.length}</span> creations
            {artItems.length > 0 && (
              <> &middot; <span className="font-bold">{artItems.length}</span> art stories</>
            )}
            {interactiveItems.length > 0 && (
              <> &middot; <span className="font-bold">{interactiveItems.length}</span> adventures</>
            )}
            {newsItems.length > 0 && (
              <> &middot; <span className="font-bold">{newsItems.length}</span> news</>
            )}
          </p>
        </motion.div>
      )}
    </div>
  )
}

export default LibraryPage
