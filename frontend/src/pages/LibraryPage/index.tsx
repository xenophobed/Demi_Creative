import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Palette, Map, Newspaper, Compass, Globe } from 'lucide-react'
import Button from '@/components/common/Button'
import Card from '@/components/common/Card'
import useStoryStore from '@/store/useStoryStore'
import useAuthStore from '@/store/useAuthStore'
import useChildStore from '@/store/useChildStore'
import { storyService } from '@/api/services/storyService'
import { libraryService } from '@/api/services/libraryService'
import type { LibraryItem, LibraryItemType, LibrarySortOrder } from '@/api/services/libraryService'
import SafetyBadge from '@/components/story/SafetyBadge'
import { useLibraryPreferences } from '@/hooks/useLibraryPreferences'
import MiniPlayer from '@/components/common/MiniPlayer'
import { getAgeLayoutConfig } from '@/config/ageConfig'
import type { NewsToKidsResponse } from '@/types/api'

// Content type tabs
type ContentTab = 'all' | 'art-stories' | 'interactive' | 'news'

const TABS: { id: ContentTab; label: string; icon: React.ReactNode }[] = [
  { id: 'all', label: 'All', icon: <BookOpen size={16} /> },
  { id: 'art-stories', label: 'Art Stories', icon: <Palette size={16} /> },
  { id: 'interactive', label: 'Interactive', icon: <Map size={16} /> },
  { id: 'news', label: 'News', icon: <Newspaper size={16} /> },
]

const SORT_OPTIONS: { value: LibrarySortOrder; label: string }[] = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'word_count', label: 'Longest First' },
]

function tabToApiType(tab: ContentTab): LibraryItemType | undefined {
  if (tab === 'art-stories') return 'art-story'
  if (tab === 'interactive') return 'interactive'
  if (tab === 'news') return 'news'
  return undefined // 'all'
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

function truncatePreview(text: string, maxLen = 120): string {
  if (!text) return ''
  return text.length > maxLen ? `${text.slice(0, maxLen)}...` : text
}

// ---- Favorite button (#63) ----

function FavoriteButton({
  itemId,
  itemType,
  isFavorited,
  onToggled,
}: {
  itemId: string
  itemType: LibraryItemType
  isFavorited: boolean
  onToggled?: () => void
}) {
  const [optimistic, setOptimistic] = useState(isFavorited)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    setOptimistic(isFavorited)
  }, [isFavorited])

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation()
    const next = !optimistic
    setOptimistic(next)
    setPending(true)
    try {
      if (next) {
        await libraryService.addFavorite(itemId, itemType)
      } else {
        await libraryService.removeFavorite(itemId, itemType)
      }
      onToggled?.()
    } catch {
      setOptimistic(!next) // revert
    } finally {
      setPending(false)
    }
  }

  return (
    <motion.button
      onClick={handleClick}
      disabled={pending}
      className="text-xl flex-shrink-0 focus:outline-none disabled:opacity-50"
      whileTap={{ scale: 0.8 }}
      title={optimistic ? 'Remove from favorites' : 'Add to favorites'}
    >
      {optimistic ? '★' : '☆'}
    </motion.button>
  )
}

// ---- Search bar (#62) ----

function SearchBar({
  onSearch,
  isLoading,
}: {
  onSearch: (query: string) => void
  isLoading: boolean
}) {
  const [query, setQuery] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.length >= 2) {
        onSearch(query)
      } else if (query.length === 0) {
        onSearch('')
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query, onSearch])

  return (
    <div className="relative">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">🔍</span>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search your library..."
        className="w-full pl-10 pr-10 py-2.5 rounded-btn bg-white/80 border border-gray-200 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none text-sm"
      />
      {isLoading && (
        <span className="absolute right-10 top-1/2 -translate-y-1/2 text-gray-400 animate-spin text-sm">
          ⏳
        </span>
      )}
      {query && (
        <button
          onClick={() => setQuery('')}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          ✕
        </button>
      )}
    </div>
  )
}

// ---- Delete modal + button ----

function ConfirmDeleteModal({
  isOpen,
  itemLabel,
  onConfirm,
  onCancel,
}: {
  isOpen: boolean
  itemLabel: string
  onConfirm: () => void
  onCancel: () => void
}) {
  if (!isOpen) return null

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          className="absolute inset-0 bg-black/40"
          onClick={onCancel}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        />
        <motion.div
          className="relative bg-white rounded-2xl shadow-xl max-w-sm w-full p-6"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        >
          <div className="text-center mb-5">
            <span className="text-4xl block mb-3">🗑️</span>
            <h3 className="text-lg font-bold text-gray-800 mb-2">Delete {itemLabel}?</h3>
            <p className="text-gray-500 text-sm">
              This will be permanently removed and cannot be undone.
            </p>
          </div>
          <div className="flex gap-3">
            <button
              className="flex-1 px-4 py-2.5 rounded-xl border-2 border-gray-200 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
              onClick={onCancel}
            >
              Cancel
            </button>
            <button
              className="flex-1 px-4 py-2.5 rounded-xl bg-red-500 text-white font-medium hover:bg-red-600 transition-colors"
              onClick={onConfirm}
            >
              Delete
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

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

// ---- subcomponents ----

function ArtStoryCard({
  item,
  onClick,
  onDelete,
  showFavorite,
  onFavoriteToggled,
  showWordCount = true,
}: {
  item: LibraryItem
  onClick: () => void
  onDelete: () => void
  showFavorite: boolean
  onFavoriteToggled?: () => void
  showWordCount?: boolean
}) {
  const [imgError, setImgError] = useState(false)
  const imgSrc = (item as any).thumbnail_url || item.image_url

  return (
    <Card className="cursor-pointer" onClick={onClick}>
      <div className="flex gap-4">
        {/* Thumbnail */}
        <div className="flex-shrink-0 w-20 h-20 rounded-lg bg-gradient-to-br from-primary/20 via-secondary/10 to-accent/20 flex items-center justify-center overflow-hidden">
          {imgSrc && !imgError ? (
            <img
              src={imgSrc.startsWith('/') ? imgSrc : '/' + imgSrc}
              alt="Artwork"
              className="w-full h-full object-cover"
              onError={() => setImgError(true)}
            />
          ) : (
            <motion.div
              whileHover={{ rotate: [0, -10, 10, 0] }}
              transition={{ duration: 0.5 }}
            >
              <Palette size={36} className="text-primary/60" strokeWidth={1.5} />
            </motion.div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <span className="text-xs font-medium px-2 py-0.5 bg-primary/10 text-primary rounded-full mb-1 inline-block">
                Art Story
              </span>
              <h3 className="font-bold text-gray-800 truncate">{item.title}</h3>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {item.safety_score !== undefined && (
                <SafetyBadge score={item.safety_score} />
              )}
              {showFavorite && (
                <FavoriteButton
                  itemId={item.id}
                  itemType="art-story"
                  isFavorited={item.is_favorited}
                  onToggled={onFavoriteToggled}
                />
              )}
            </div>
          </div>

          <p className="text-gray-500 text-sm mt-1 line-clamp-2">
            {truncatePreview(item.preview)}
          </p>

          <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
            {showWordCount && item.word_count !== undefined && (
              <span className="flex items-center gap-1">
                <span>📝</span>
                {item.word_count} words
              </span>
            )}
            <span className="flex items-center gap-1">
              <span>🕐</span>
              {formatDate(item.created_at)}
            </span>
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
          {item.audio_url && (
            <MiniPlayer itemId={item.id} audioUrl={item.audio_url} />
          )}
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

function InteractiveStoryCard({
  item,
  onClick,
  onDelete,
  showFavorite,
  onFavoriteToggled,
}: {
  item: LibraryItem
  onClick: () => void
  onDelete: () => void
  showFavorite: boolean
  onFavoriteToggled?: () => void
}) {
  const progress = item.progress ?? 0

  return (
    <Card className="cursor-pointer" onClick={onClick}>
      <div className="flex gap-4">
        {/* Icon */}
        <div className="flex-shrink-0 w-20 h-20 rounded-lg bg-gradient-to-br from-secondary/20 via-accent/10 to-primary/20 flex items-center justify-center">
          <motion.div
            whileHover={{ scale: 1.1 }}
            transition={{ duration: 0.3 }}
          >
            <Compass size={36} className="text-secondary/60" strokeWidth={1.5} />
          </motion.div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <span className="text-xs font-medium px-2 py-0.5 bg-secondary/10 text-secondary rounded-full mb-1 inline-block">
                Interactive Story
              </span>
              <h3 className="font-bold text-gray-800 truncate">{item.title}</h3>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
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
              {showFavorite && (
                <FavoriteButton
                  itemId={item.id}
                  itemType="interactive"
                  isFavorited={item.is_favorited}
                  onToggled={onFavoriteToggled}
                />
              )}
            </div>
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

function NewsCard({
  item,
  onClick,
  onDelete,
  showFavorite,
  onFavoriteToggled,
}: {
  item: LibraryItem
  onClick: () => void
  onDelete: () => void
  showFavorite: boolean
  onFavoriteToggled?: () => void
}) {
  return (
    <Card className="cursor-pointer" onClick={onClick}>
      <div className="flex gap-4">
        {/* Icon */}
        <div className="flex-shrink-0 w-20 h-20 rounded-lg bg-gradient-to-br from-accent/20 via-primary/10 to-secondary/20 flex items-center justify-center">
          <motion.div
            whileHover={{ rotate: [0, -5, 5, 0] }}
            transition={{ duration: 0.5 }}
          >
            <Globe size={36} className="text-accent/60" strokeWidth={1.5} />
          </motion.div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <span className="text-xs font-medium px-2 py-0.5 bg-accent/10 text-accent rounded-full mb-1 inline-block">
                {item.category
                  ? item.category.charAt(0).toUpperCase() + item.category.slice(1)
                  : 'News'}
              </span>
              <h3 className="font-bold text-gray-800 truncate">{item.title}</h3>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {item.safety_score !== undefined && (
                <SafetyBadge score={item.safety_score} />
              )}
              {showFavorite && (
                <FavoriteButton
                  itemId={item.id}
                  itemType="news"
                  isFavorited={item.is_favorited}
                  onToggled={onFavoriteToggled}
                />
              )}
            </div>
          </div>

          <p className="text-gray-500 text-sm mt-1 line-clamp-2">
            {truncatePreview(item.preview)}
          </p>

          <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
            {item.word_count !== undefined && item.word_count > 0 && (
              <span className="flex items-center gap-1">
                <span>📝</span>
                {item.word_count} words
              </span>
            )}
            <span className="flex items-center gap-1">
              <span>🕐</span>
              {formatDate(item.created_at)}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex-shrink-0 flex flex-col items-center justify-between py-1">
          <DeleteButton onDelete={onDelete} />
          {item.audio_url && (
            <MiniPlayer itemId={item.id} audioUrl={item.audio_url} />
          )}
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

// ---- list row (compact view) ----

const TYPE_BADGE: Record<LibraryItemType, { label: string; color: string }> = {
  'art-story': { label: 'Art Story', color: 'bg-primary/10 text-primary' },
  interactive: { label: 'Interactive', color: 'bg-secondary/10 text-secondary' },
  news: { label: 'News', color: 'bg-accent/10 text-accent' },
}

function ListRow({
  item,
  onClick,
  onDelete,
}: {
  item: LibraryItem
  onClick: () => void
  onDelete: () => void
}) {
  const [imgError, setImgError] = useState(false)
  const imgSrc = (item as any).thumbnail_url || item.image_url
  const badge = TYPE_BADGE[item.type]

  return (
    <motion.div
      className="flex items-center gap-3 px-3 py-2 rounded-xl bg-white/80 hover:bg-white cursor-pointer transition-colors border border-gray-100"
      onClick={onClick}
      whileHover={{ x: 2 }}
    >
      {/* Mini thumbnail */}
      <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center overflow-hidden">
        {imgSrc && !imgError ? (
          <img
            src={imgSrc.startsWith('/') ? imgSrc : '/' + imgSrc}
            alt=""
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <span className="text-lg">{item.type === 'art-story' ? '📖' : item.type === 'interactive' ? '🌿' : '📰'}</span>
        )}
      </div>

      {/* Title + badge */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${badge.color}`}>
            {badge.label}
          </span>
          <h4 className="text-sm font-semibold text-gray-800 truncate">{item.title}</h4>
        </div>
      </div>

      {/* Meta */}
      <div className="flex items-center gap-3 text-xs text-gray-400 flex-shrink-0">
        {item.word_count !== undefined && <span>{item.word_count}w</span>}
        <span className="hidden sm:inline">
          {new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </span>
      </div>

      {/* Audio + Delete */}
      {item.audio_url && <MiniPlayer itemId={item.id} audioUrl={item.audio_url} />}
      <DeleteButton onDelete={onDelete} />
    </motion.div>
  )
}

// ---- main page ----

function LibraryPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { storyHistory, clearHistory, setCurrentStory, removeStory } = useStoryStore()
  const { isAuthenticated } = useAuthStore()
  const { currentChild, defaultChildId } = useChildStore()
  const { viewMode, toggleViewMode } = useLibraryPreferences()
  const ageLayout = getAgeLayoutConfig(currentChild?.age_group)

  const [activeTab, setActiveTab] = useState<ContentTab>('all')
  const [sortOrder, setSortOrder] = useState<LibrarySortOrder>('newest')
  const [searchQuery, setSearchQuery] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<LibraryItem | null>(null)
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const [pageSize] = useState(20)
  const [offset, setOffset] = useState(0)

  const childId = currentChild?.child_id || defaultChildId
  const isSearching = searchQuery.length >= 2

  // Reset offset when tab, sort, or search changes
  useEffect(() => {
    setOffset(0)
  }, [activeTab, sortOrder, searchQuery])

  // ---- data fetching (#61 — unified API for authenticated users) ----

  const apiType = tabToApiType(activeTab)

  // Unified library (authenticated, not searching)
  const {
    data: libraryData,
    isLoading: libraryLoading,
  } = useQuery({
    queryKey: ['library', activeTab, sortOrder, offset, pageSize],
    queryFn: () =>
      libraryService.getLibrary({
        type: apiType,
        sort: sortOrder,
        limit: pageSize,
        offset,
      }),
    enabled: isAuthenticated && !isSearching,
  })

  // Search (authenticated, searching)
  const {
    data: searchData,
    isLoading: searchLoading,
  } = useQuery({
    queryKey: ['library-search', searchQuery, activeTab, sortOrder, offset],
    queryFn: () =>
      libraryService.searchLibrary({
        q: searchQuery,
        type: apiType,
        sort: sortOrder,
        limit: pageSize,
        offset,
      }),
    enabled: isAuthenticated && isSearching,
  })

  // Fallback: local stories (unauthenticated)
  const { data: childArtStories } = useQuery({
    queryKey: ['library-child-art-stories', childId],
    queryFn: () => storyService.getStoryHistory(childId),
    enabled: !!childId && !isAuthenticated,
  })

  // Fallback: news by child_id (unauthenticated)
  const { data: newsHistory } = useQuery({
    queryKey: ['library-news-history', childId],
    queryFn: () => storyService.getNewsHistory(childId),
    enabled: !!childId && !isAuthenticated,
  })

  // ---- build items ----

  const activeData = isSearching ? searchData : libraryData
  const isLoading = isSearching ? searchLoading : libraryLoading

  // Authenticated: use unified API response
  const serverItems: LibraryItem[] = isAuthenticated ? (activeData?.items ?? []) : []
  const serverTotal = isAuthenticated ? (activeData?.total ?? 0) : 0

  // Unauthenticated: build from local stores (existing fallback behavior)
  const localItems: LibraryItem[] = !isAuthenticated
    ? buildLocalItems(storyHistory, childArtStories, newsHistory, activeTab, searchQuery)
    : []

  // Filter out items being deleted
  const filterDeleting = (items: LibraryItem[]) =>
    items.filter((i) => !deletingIds.has(i.id))

  const visibleItems = filterDeleting(isAuthenticated ? serverItems : localItems)
  const totalItems = isAuthenticated ? serverTotal : localItems.length
  const hasMore = isAuthenticated && offset + pageSize < serverTotal

  // ---- handlers ----

  const handleSearch = useCallback((q: string) => {
    setSearchQuery(q)
  }, [])

  const handleItemClick = (item: LibraryItem) => {
    if (item.type === 'art-story') {
      const localStory = storyHistory.find((s) => s.story_id === item.id)
      setCurrentStory(localStory ?? null)
      navigate(`/story/${item.id}`)
    } else if (item.type === 'interactive') {
      navigate(`/interactive?session=${item.id}`)
    } else if (item.type === 'news') {
      navigate(`/news`)
    }
  }

  const handleDeleteItem = useCallback(async (item: LibraryItem) => {
    setDeletingIds((prev) => new Set(prev).add(item.id))

    if (item.type !== 'interactive') {
      removeStory(item.id)
    }

    try {
      if (item.type === 'interactive') {
        await storyService.deleteSession(item.id)
      } else {
        await storyService.deleteStory(item.id)
      }
    } catch {
      // Server deletion failed — local removal already happened
    }

    queryClient.invalidateQueries({ queryKey: ['library'] })
    queryClient.invalidateQueries({ queryKey: ['library-search'] })
    queryClient.invalidateQueries({ queryKey: ['library-child-art-stories'] })
    queryClient.invalidateQueries({ queryKey: ['library-news-history'] })
  }, [queryClient, removeStory])

  const handleClearHistory = () => {
    if (
      window.confirm(
        'Are you sure you want to clear all local story history? This cannot be undone.'
      )
    ) {
      clearHistory()
    }
  }

  const handleLoadMore = () => {
    setOffset((prev) => prev + pageSize)
  }

  const handleFavoriteToggled = () => {
    queryClient.invalidateQueries({ queryKey: ['library'] })
    queryClient.invalidateQueries({ queryKey: ['library-search'] })
  }

  // ---- render ----

  return (
    <div className={`space-y-6 ${ageLayout.fontSize}`}>
      {/* Page header */}
      <motion.div
        className="flex items-center justify-between"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <BookOpen size={28} className="text-primary" />
          My Library
        </h1>
        <div className="flex items-center gap-2">
          <motion.button
            onClick={toggleViewMode}
            className="p-2 rounded-lg text-gray-500 hover:text-primary hover:bg-primary/10 transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            title={viewMode === 'grid' ? 'Switch to list view' : 'Switch to grid view'}
          >
            {viewMode === 'grid' ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
                <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
              </svg>
            )}
          </motion.button>
          {storyHistory.length > 0 && !isAuthenticated && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearHistory}
              className="text-gray-500"
            >
              Clear Local History
            </Button>
          )}
        </div>
      </motion.div>

      {/* Search bar (#62) */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
      >
        <SearchBar onSearch={handleSearch} isLoading={searchLoading} />
      </motion.div>

      {/* Tab bar + sort dropdown (#65) */}
      <motion.div
        className="flex items-center justify-between gap-2"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex gap-2 overflow-x-auto pb-1">
          {TABS.map((tab) => (
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
              {tab.icon}
              <span>{tab.label}</span>
            </motion.button>
          ))}
        </div>

        <select
          value={sortOrder}
          onChange={(e) => setSortOrder(e.target.value as LibrarySortOrder)}
          className="flex-shrink-0 text-sm px-3 py-2 rounded-btn bg-white/80 border border-gray-200 text-gray-600 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none cursor-pointer"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </motion.div>

      {/* Loading indicator */}
      {isLoading && visibleItems.length === 0 && (
        <motion.div
          className="text-center py-4 text-gray-400 text-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {isSearching ? 'Searching...' : 'Loading your library...'}
        </motion.div>
      )}

      {/* Content — grid or list */}
      <AnimatePresence mode="popLayout">
        {visibleItems.length > 0 ? (
          <motion.div className={viewMode === 'grid' ? `grid ${ageLayout.gridClass} gap-4` : 'space-y-2'}>
            {visibleItems.map((item, index) => (
              <motion.div
                key={`${item.type}-${item.id}`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -100 }}
                transition={{ delay: Math.min(index * 0.04, 0.3) }}
              >
                {viewMode === 'list' ? (
                  <ListRow item={item} onClick={() => handleItemClick(item)} onDelete={() => setDeleteTarget(item)} />
                ) : (
                  <>
                    {item.type === 'art-story' && (
                      <ArtStoryCard
                        item={item}
                        onClick={() => handleItemClick(item)}
                        onDelete={() => setDeleteTarget(item)}
                        showFavorite={isAuthenticated}
                        onFavoriteToggled={handleFavoriteToggled}
                        showWordCount={ageLayout.showWordCount}
                      />
                    )}
                    {item.type === 'interactive' && (
                      <InteractiveStoryCard
                        item={item}
                        onClick={() => handleItemClick(item)}
                        onDelete={() => setDeleteTarget(item)}
                        showFavorite={isAuthenticated}
                        onFavoriteToggled={handleFavoriteToggled}
                      />
                    )}
                    {item.type === 'news' && (
                      <NewsCard
                        item={item}
                        onClick={() => handleItemClick(item)}
                        onDelete={() => setDeleteTarget(item)}
                        showFavorite={isAuthenticated}
                        onFavoriteToggled={handleFavoriteToggled}
                      />
                    )}
                  </>
                )}
              </motion.div>
            ))}

            {/* Load more */}
            {hasMore && (
              <motion.div
                className="text-center pt-2"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLoadMore}
                  isLoading={isLoading && offset > 0}
                >
                  Load More
                </Button>
              </motion.div>
            )}
          </motion.div>
        ) : !isLoading ? (
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
              {isSearching ? '🔍' : '📭'}
            </motion.div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">
              {isSearching
                ? 'No results found'
                : activeTab === 'all'
                ? 'Nothing here yet'
                : activeTab === 'art-stories'
                ? 'No art stories yet'
                : activeTab === 'interactive'
                ? 'No interactive stories yet'
                : 'No news conversions yet'}
            </h2>
            <p className="text-gray-500 mb-6">
              {isSearching
                ? 'Try a different search term or clear the search.'
                : activeTab === 'news'
                ? 'Visit the News Explorer to convert articles for kids!'
                : activeTab === 'interactive'
                ? 'Try the Interactive Story mode to create branching adventures!'
                : 'Upload your first artwork and start creating amazing stories!'}
            </p>
            {!isSearching && (
              <Link to={activeTab === 'news' ? '/news' : activeTab === 'interactive' ? '/interactive' : '/upload'}>
                <Button size="lg" leftIcon={<span>✨</span>}>
                  {activeTab === 'news'
                    ? 'Go to News Explorer'
                    : activeTab === 'interactive'
                    ? 'Start an Adventure'
                    : 'Start Creating'}
                </Button>
              </Link>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>

      {/* Footer statistics */}
      {totalItems > 0 && !isSearching && (
        <motion.div
          className="text-center py-4 text-gray-500"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <p>
            Total:{' '}
            <span className="font-bold text-primary">{totalItems}</span> creations
          </p>
        </motion.div>
      )}

      {/* Delete confirmation modal */}
      <ConfirmDeleteModal
        isOpen={deleteTarget !== null}
        itemLabel={
          deleteTarget?.type === 'art-story' ? 'this art story' :
          deleteTarget?.type === 'interactive' ? 'this interactive story' : 'this news article'
        }
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            handleDeleteItem(deleteTarget)
            setDeleteTarget(null)
          }
        }}
      />
    </div>
  )
}

// ---- Local fallback for unauthenticated users ----

function buildLocalItems(
  storyHistory: any[],
  childArtStories: any[] | undefined,
  newsHistory: NewsToKidsResponse[] | undefined,
  activeTab: ContentTab,
  searchQuery: string,
): LibraryItem[] {
  const items: LibraryItem[] = []
  const queryLower = searchQuery.toLowerCase()

  // Art stories
  if (activeTab === 'all' || activeTab === 'art-stories') {
    const stories = childArtStories && childArtStories.length > 0
      ? childArtStories
      : storyHistory

    for (const s of stories) {
      const text = s.story?.text || s.story_text || ''
      const item: LibraryItem = {
        id: s.story_id,
        type: 'art-story',
        title: `Story #${s.story_id.slice(0, 8)}`,
        preview: text.slice(0, 150),
        image_url: s.image_url ?? null,
        audio_url: s.audio_url ?? null,
        created_at: s.created_at,
        is_favorited: false,
        safety_score: s.safety_score,
        word_count: s.story?.word_count || s.word_count || 0,
        themes: s.educational_value?.themes || s.themes || [],
      }

      if (!searchQuery || text.toLowerCase().includes(queryLower)) {
        items.push(item)
      }
    }
  }

  // News
  if ((activeTab === 'all' || activeTab === 'news') && newsHistory) {
    for (const n of newsHistory) {
      const item: LibraryItem = {
        id: n.conversion_id,
        type: 'news',
        title: n.kid_title,
        preview: n.kid_content,
        image_url: null,
        audio_url: n.audio_url ?? null,
        created_at: n.created_at as unknown as string,
        is_favorited: false,
        category: n.category,
      }

      if (!searchQuery || `${n.kid_title} ${n.kid_content}`.toLowerCase().includes(queryLower)) {
        items.push(item)
      }
    }
  }

  // Sort by date descending
  items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  return items
}

export default LibraryPage
