/**
 * GrowthTimeline — Pure SVG bar chart for creation frequency (#134)
 *
 * Shows creation counts grouped by week or month.
 * No external chart library — lightweight SVG rendering.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { TrendingUp } from 'lucide-react'
import { libraryService } from '@/api/services/libraryService'
import type { StatsGroupBy, LibraryStatsPeriod } from '@/api/services/libraryService'

// ---- SVG Bar Chart ----

const CHART_HEIGHT = 180
const BAR_GAP = 6
const LABEL_HEIGHT = 32
const Y_AXIS_WIDTH = 36
const BAR_WIDTH = 24
const CELL_WIDTH = BAR_WIDTH + BAR_GAP * 2

function formatPeriodLabel(period: string, groupBy: StatsGroupBy): string {
  if (groupBy === 'month') {
    // "2026-03" → "Mar"
    const [, month] = period.split('-')
    const date = new Date(2000, parseInt(month, 10) - 1)
    return date.toLocaleString('en-US', { month: 'short' })
  }
  // "2026-W10" → "W10"
  const match = period.match(/W(\d+)/)
  return match ? `W${match[1]}` : period
}

function BarChart({
  periods,
  groupBy,
}: {
  periods: LibraryStatsPeriod[]
  groupBy: StatsGroupBy
}) {
  const maxCount = Math.max(...periods.map((p) => p.count), 1)
  // Round up to a nice tick ceiling (multiples of 2 for small, 5 for larger)
  const tickStep = maxCount <= 6 ? 2 : 5
  const tickMax = Math.ceil(maxCount / tickStep) * tickStep || tickStep

  const barAreaWidth = periods.length * CELL_WIDTH
  const svgWidth = barAreaWidth + Y_AXIS_WIDTH + 16
  const svgHeight = CHART_HEIGHT + LABEL_HEIGHT + 12

  // Generate evenly spaced ticks
  const tickCount = Math.min(tickMax / tickStep, 5)
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) =>
    Math.round((i * tickMax) / tickCount)
  )

  return (
    <div className="overflow-x-auto -mx-2 px-2">
      <svg
        width={svgWidth}
        height={svgHeight}
        className="block"
        role="img"
        aria-label="Creation frequency chart"
      >
        {/* Y-axis ticks + grid lines */}
        {ticks.map((tick) => {
          const y = CHART_HEIGHT - (tick / tickMax) * CHART_HEIGHT + 6
          return (
            <g key={tick}>
              <text
                x={Y_AXIS_WIDTH - 6}
                y={y}
                textAnchor="end"
                className="fill-gray-400"
                fontSize={11}
                dominantBaseline="middle"
              >
                {tick}
              </text>
              <line
                x1={Y_AXIS_WIDTH}
                y1={y}
                x2={svgWidth - 8}
                y2={y}
                stroke="#e5e7eb"
                strokeWidth={1}
                strokeDasharray={tick === 0 ? undefined : '4 3'}
              />
            </g>
          )
        })}

        {/* Bars */}
        {periods.map((p, i) => {
          const x = Y_AXIS_WIDTH + 8 + i * CELL_WIDTH + BAR_GAP
          const barH = Math.max((p.count / tickMax) * CHART_HEIGHT, p.count > 0 ? 4 : 0)
          const y = CHART_HEIGHT - barH + 6

          return (
            <g key={p.period}>
              <motion.rect
                x={x}
                y={y}
                width={BAR_WIDTH}
                height={barH}
                rx={4}
                className="fill-primary/70 hover:fill-primary transition-colors"
                initial={{ height: 0, y: CHART_HEIGHT + 6 }}
                animate={{ height: barH, y }}
                transition={{ duration: 0.5, delay: i * 0.05 }}
              />
              {/* Count label on top of bar */}
              {p.count > 0 && (
                <text
                  x={x + BAR_WIDTH / 2}
                  y={y - 6}
                  textAnchor="middle"
                  className="fill-gray-600"
                  fontSize={11}
                  fontWeight={600}
                >
                  {p.count}
                </text>
              )}
              {/* X-axis label */}
              <text
                x={x + BAR_WIDTH / 2}
                y={CHART_HEIGHT + 22}
                textAnchor="middle"
                className="fill-gray-500"
                fontSize={10}
              >
                {formatPeriodLabel(p.period, groupBy)}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// ---- Empty State ----

function EmptyState() {
  return (
    <motion.div
      className="flex flex-col items-center justify-center py-16 text-center"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <div className="text-5xl mb-4">
        <TrendingUp size={48} className="text-gray-300 mx-auto" />
      </div>
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
    queryKey: ['library-stats', groupBy],
    queryFn: () => libraryService.getStats(groupBy),
  })

  const periods = data?.periods ?? []
  const totalCreations = periods.reduce((sum, p) => sum + p.count, 0)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Header with group-by toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp size={18} className="text-primary" />
          <span className="text-sm font-semibold text-gray-700">
            Growth Timeline
          </span>
          {totalCreations > 0 && (
            <span className="text-xs text-gray-400">
              ({totalCreations} total)
            </span>
          )}
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

      {/* Chart area */}
      <div className="bg-white rounded-2xl border border-gray-200/80 p-4 shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          </div>
        ) : periods.length === 0 ? (
          <EmptyState />
        ) : (
          <BarChart periods={periods} groupBy={groupBy} />
        )}
      </div>
    </motion.div>
  )
}
