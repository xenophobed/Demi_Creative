/**
 * GrowthTimeline — Rich growth dashboard for creative development (#356)
 *
 * Replaces the flat creation-count bar chart with meaningful metrics:
 * word count trend, theme diversity, completion rate, content mix, and streak.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { TrendingUp } from 'lucide-react'
import { libraryService } from '@/api/services/libraryService'
import type { StatsGroupBy, RichStatsPeriod } from '@/api/services/libraryService'

// ---- Metric Card ----

function MetricCard({
  icon,
  label,
  value,
  sub,
  trend,
}: {
  icon: string
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'flat'
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
        {trend && <span className={`text-sm font-semibold ${trendColor}`}>{trendIcon}</span>}
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

function ContentMixBar({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((s, v) => s + v, 0)
  if (total === 0) return null

  const colors: Record<string, string> = {
    image_to_story: 'bg-violet-400',
    kids_daily: 'bg-sky-400',
    interactive: 'bg-emerald-400',
    news_to_kids: 'bg-amber-400',
    morning_show: 'bg-sky-400',
  }

  const labels: Record<string, string> = {
    image_to_story: '🎨 Art',
    kids_daily: '🎙️ Podcast',
    interactive: '🎭 Interactive',
    news_to_kids: '📰 News',
    morning_show: '🎙️ Podcast',
  }

  return (
    <div className="space-y-1.5">
      <div className="flex h-3 rounded-full overflow-hidden">
        {Object.entries(breakdown).map(([type, count]) => (
          <div
            key={type}
            className={`${colors[type] || 'bg-gray-300'} transition-all`}
            style={{ width: `${(count / total) * 100}%` }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {Object.entries(breakdown).map(([type, count]) => (
          <span key={type} className="text-[10px] text-gray-400">
            {labels[type] || type} {count}
          </span>
        ))}
      </div>
    </div>
  )
}

// ---- Streak Badge ----

function StreakBadge({ days }: { days: number }) {
  if (days < 1) return null
  return (
    <motion.div
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-orange-400 to-amber-400 text-white text-sm font-bold shadow-md"
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      <span>🔥</span>
      <span>{days}-day streak!</span>
    </motion.div>
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

function EmptyState() {
  return (
    <motion.div
      className="flex flex-col items-center justify-center py-16 text-center"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <TrendingUp size={48} className="text-gray-300 mx-auto mb-4" />
      <h3 className="text-lg font-semibold text-gray-600 mb-2">
        Your growth story starts here!
      </h3>
      <p className="text-sm text-gray-400 max-w-xs">
        Create your first story, and watch your creative journey unfold over time.
      </p>
    </motion.div>
  )
}

// ---- Main Component ----

export default function GrowthTimeline() {
  const [groupBy, setGroupBy] = useState<StatsGroupBy>('week')

  const { data, isLoading } = useQuery({
    queryKey: ['library-stats-rich', groupBy],
    queryFn: () => libraryService.getRichStats(groupBy),
  })

  const periods = data?.periods ?? []
  const streak = data?.streak_days ?? 0

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

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Header with toggle + streak */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <TrendingUp size={18} className="text-primary" />
          <span className="text-sm font-semibold text-gray-700">Growth Dashboard</span>
          <StreakBadge days={streak} />
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
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {/* Metric cards grid */}
          <div className="grid grid-cols-2 gap-3">
            <MetricCard
              icon="✍️"
              label="Total Words"
              value={totalWords.toLocaleString()}
              sub={latest ? `${latest.total_words.toLocaleString()} this ${groupBy}` : undefined}
              trend={getTrend(periods, 'total_words')}
            />
            <MetricCard
              icon="🎨"
              label="Themes Explored"
              value={latest?.unique_themes ?? 0}
              sub={`this ${groupBy}`}
              trend={getTrend(periods, 'unique_themes')}
            />
            <MetricCard
              icon="🎭"
              label="Completion"
              value={latest ? `${Math.round(latest.completion_rate * 100)}%` : '—'}
              sub="interactive stories"
              trend={getTrend(periods, 'completion_rate')}
            />
            <MetricCard
              icon="📚"
              label="Creations"
              value={totalCreations}
              sub={latest ? `${latest.creation_count} this ${groupBy}` : undefined}
              trend={getTrend(periods, 'creation_count')}
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
