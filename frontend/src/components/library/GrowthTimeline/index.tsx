/**
 * GrowthTimeline — Rich growth dashboard for creative development (#356)
 *
 * Replaces the flat creation-count bar chart with meaningful metrics:
 * word count trend, theme diversity, completion rate, and content mix.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { TrendingUp } from 'lucide-react'
import { libraryService } from '@/api/services/libraryService'
import type { StatsGroupBy, RichStatsPeriod } from '@/api/services/libraryService'
import useAuthStore from '@/store/useAuthStore'

// ---- Metric Card ----

function MetricCard({
  icon,
  label,
  value,
  sub,
  trend,
  showTrend,
}: {
  icon: string
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'flat'
  showTrend?: boolean
}) {
  const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : ''
  const trendColor = trend === 'up' ? 'text-emerald-500' : trend === 'down' ? 'text-red-400' : ''

  return (
    <motion.div
      className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{icon}</span>
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</span>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold text-gray-800">{value}</span>
        {showTrend !== false && trend && (
          <span className={`text-sm font-semibold ${trendColor}`}>{trendIcon}</span>
        )}
      </div>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </motion.div>
  )
}

// ---- Word Count Mini Chart ----

function WordTrendChart({ periods }: { periods: RichStatsPeriod[] }) {
  if (periods.length < 2) return null

  const values = periods.map((p) => p.total_words)
  const max = Math.max(...values, 1)
  const width = 240
  const height = 48
  const step = width / (values.length - 1)

  const points = values.map((v, i) => `${i * step},${height - (v / max) * height}`).join(' ')

  return (
    <svg width={width} height={height} className="block mt-2">
      <polyline
        fill="none"
        stroke="url(#wordGrad)"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
      <defs>
        <linearGradient id="wordGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#34d399" />
        </linearGradient>
      </defs>
    </svg>
  )
}

// ---- Content Mix Bar ----

const MIX_META: Record<string, { icon: string; label: string; color: string; ring: string }> = {
  image_to_story: { icon: '🎨', label: 'Art Story', color: '#8b5cf6', ring: 'ring-violet-300' },
  kids_daily:     { icon: '🎙️', label: 'Podcast',   color: '#0ea5e9', ring: 'ring-sky-300' },
  interactive:    { icon: '🎭', label: 'Interactive', color: '#10b981', ring: 'ring-emerald-300' },
  news_to_kids:   { icon: '📰', label: 'News',       color: '#f59e0b', ring: 'ring-amber-300' },
  morning_show:   { icon: '🎙️', label: 'Podcast',   color: '#0ea5e9', ring: 'ring-sky-300' },
}

function ContentMixBar({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((s, v) => s + v, 0)
  if (total === 0) return null

  // Sort by count descending
  const entries = Object.entries(breakdown).sort((a, b) => b[1] - a[1])

  // Build donut ring segments
  const RADIUS = 40
  const CIRCUMFERENCE = 2 * Math.PI * RADIUS
  let offset = 0

  return (
    <div className="flex items-center gap-5">
      {/* Donut chart */}
      <div className="relative flex-shrink-0">
        <svg width={100} height={100} viewBox="0 0 100 100">
          {entries.map(([type, count]) => {
            const meta = MIX_META[type] || { color: '#9ca3af' }
            const pct = count / total
            const dashLen = pct * CIRCUMFERENCE
            const dashGap = CIRCUMFERENCE - dashLen
            const currentOffset = offset
            offset += dashLen

            return (
              <motion.circle
                key={type}
                cx={50}
                cy={50}
                r={RADIUS}
                fill="none"
                stroke={meta.color}
                strokeWidth={12}
                strokeLinecap="round"
                strokeDasharray={`${dashLen} ${dashGap}`}
                strokeDashoffset={-currentOffset}
                initial={{ strokeDasharray: `0 ${CIRCUMFERENCE}` }}
                animate={{ strokeDasharray: `${dashLen} ${dashGap}` }}
                transition={{ duration: 0.8, delay: 0.1 }}
                style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%' }}
              />
            )
          })}
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold text-gray-700">{total}</span>
        </div>
      </div>

      {/* Legend pills */}
      <div className="flex flex-col gap-2 min-w-0">
        {entries.map(([type, count]) => {
          const meta = MIX_META[type] || { icon: '📄', label: type, color: '#9ca3af', ring: 'ring-gray-300' }
          const pct = Math.round((count / total) * 100)

          return (
            <motion.div
              key={type}
              className="flex items-center gap-2"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
            >
              <span
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: meta.color }}
              />
              <span className="text-sm text-gray-600 truncate">
                {meta.icon} {meta.label}
              </span>
              <span className="text-sm font-semibold text-gray-800 ml-auto">{count}</span>
              <span className="text-xs text-gray-400 w-9 text-right">{pct}%</span>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

// ---- Trend helper ----

function getTrend(periods: RichStatsPeriod[], key: keyof RichStatsPeriod): 'up' | 'down' | 'flat' {
  if (periods.length < 2) return 'flat'
  const curr = periods[periods.length - 1][key] as number
  const prev = periods[periods.length - 2][key] as number
  if (curr > prev) return 'up'
  if (curr < prev) return 'down'
  return 'flat'
}

// ---- Empty State ----

function EmptyState({ isParentDashboard }: { isParentDashboard?: boolean }) {
  return (
    <motion.div
      className="flex flex-col items-center justify-center py-16 text-center"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <TrendingUp size={48} className="text-gray-300 mx-auto mb-4" />
      <h3 className="text-lg font-semibold text-gray-600 mb-2">
        {isParentDashboard ? "Creativity insights will appear here" : "Your growth story starts here!"}
      </h3>
      <p className="text-sm text-gray-400 max-w-xs">
        {isParentDashboard
          ? "Try an open-ended drawing or story prompt when your child feels ready."
          : "Create your first story, and watch your creative journey unfold over time."}
      </p>
    </motion.div>
  )
}

// ---- Main Component ----

export default function GrowthTimeline({
  childId,
  isParentDashboard = false,
}: {
  childId?: string | null
  isParentDashboard?: boolean
}) {
  const [groupBy, setGroupBy] = useState<StatsGroupBy>('week')
  const userId = useAuthStore((state) => state.user?.user_id ?? 'anonymous')

  const { data, isLoading } = useQuery({
    queryKey: ['library-stats-rich', userId, childId ?? 'all-children', isParentDashboard, groupBy],
    queryFn: () => libraryService.getRichStats(groupBy, { childId, parentDashboard: isParentDashboard }),
  })

  const periods = data?.periods ?? []

  // Aggregate latest period for headline metrics
  const latest = periods.length > 0 ? periods[periods.length - 1] : null
  const totalWords = periods.reduce((s, p) => s + p.total_words, 0)
  const totalCreations = periods.reduce((s, p) => s + p.creation_count, 0)

  // Aggregate content mix across all periods
  const allMix: Record<string, number> = {}
  for (const p of periods) {
    for (const [type, count] of Object.entries(p.story_type_breakdown)) {
      allMix[type] = (allMix[type] || 0) + count
    }
  }
  const contentTypeCount = Object.keys(allMix).length

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Header with toggle */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <TrendingUp size={18} className="text-primary" />
          <span className="text-sm font-semibold text-gray-700">
            {isParentDashboard ? "Parent Creativity Dashboard" : "Growth Dashboard"}
          </span>
        </div>
        <div className="flex bg-gray-100 rounded-lg p-0.5">
          {(['week', 'month'] as StatsGroupBy[]).map((option) => (
            <button
              key={option}
              onClick={() => setGroupBy(option)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                groupBy === option
                  ? 'bg-white text-primary shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {option === 'week' ? 'Weekly' : 'Monthly'}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        </div>
      ) : periods.length === 0 ? (
        <EmptyState isParentDashboard={isParentDashboard} />
      ) : (
        <div className="space-y-4">
          {/* Metric cards grid */}
          <div className="grid grid-cols-2 gap-3">
            <MetricCard
              icon="✍️"
              label="Story Words"
              value={totalWords.toLocaleString()}
              sub={latest ? `${latest.total_words.toLocaleString()} this ${groupBy}` : undefined}
              trend={getTrend(periods, 'total_words')}
              showTrend={!isParentDashboard}
            />
            <MetricCard
              icon="🎨"
              label="Themes Explored"
              value={latest?.unique_themes ?? 0}
              sub={`this ${groupBy}`}
              trend={getTrend(periods, 'unique_themes')}
              showTrend={!isParentDashboard}
            />
            {isParentDashboard ? (
              <MetricCard
                icon="🎭"
                label="Formats Tried"
                value={contentTypeCount}
                sub="creative modes"
                showTrend={false}
              />
            ) : (
              <MetricCard
                icon="🎭"
                label="Completion"
                value={latest ? `${Math.round(latest.completion_rate * 100)}%` : '—'}
                sub="interactive stories"
                trend={getTrend(periods, 'completion_rate')}
              />
            )}
            <MetricCard
              icon="📚"
              label="Creations"
              value={totalCreations}
              sub={latest ? `${latest.creation_count} this ${groupBy}` : undefined}
              trend={getTrend(periods, 'creation_count')}
              showTrend={!isParentDashboard}
            />
          </div>

          {/* Word count trend */}
          <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
              Word Count Trend
            </p>
            <WordTrendChart periods={periods} />
            <div className="flex justify-between text-[10px] text-gray-300 mt-1">
              <span>{periods[0]?.period}</span>
              <span>{periods[periods.length - 1]?.period}</span>
            </div>
          </div>

          {/* Content mix */}
          <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
              Content Mix
            </p>
            <ContentMixBar breakdown={allMix} />
          </div>
        </div>
      )}
    </motion.div>
  )
}
