import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { CharacterMemory, EducationalValue } from '@/types/api'

type TabType = 'characters' | 'learning' | 'analysis'

interface TabbedMetadataProps {
  characters: CharacterMemory[]
  educationalValue: EducationalValue
  analysis: Record<string, unknown>
  safetyScore: number
  className?: string
}

/**
 * TabbedMetadata - Collapsible tabbed section for story metadata
 *
 * Features:
 * - Three tabs: Characters, Learning, Art Analysis
 * - Only one expanded at a time
 * - Smooth expand/collapse animation
 * - Collapses to accordion on mobile
 */
function TabbedMetadata({
  characters,
  educationalValue,
  analysis,
  safetyScore,
  className = '',
}: TabbedMetadataProps) {
  const [activeTab, setActiveTab] = useState<TabType | null>(null)

  const toggleTab = (tab: TabType) => {
    setActiveTab(activeTab === tab ? null : tab)
  }

  const tabs = [
    {
      id: 'characters' as TabType,
      icon: '👥',
      label: 'Characters',
      count: characters.length,
    },
    {
      id: 'learning' as TabType,
      icon: '📚',
      label: 'Learning',
      count: educationalValue.themes.length + educationalValue.concepts.length,
    },
    {
      id: 'analysis' as TabType,
      icon: '🔍',
      label: 'Art Analysis',
      count: Object.keys(analysis).length,
    },
  ]

  return (
    <div className={`tabbed-metadata ${className}`}>
      {/* Safety badge */}
      <div className="tabbed-metadata-safety">
        <span className="safety-icon">⭐</span>
        <span className="safety-label">Safety Score:</span>
        <span className="safety-value">{Math.round(safetyScore * 100)}%</span>
      </div>

      {/* Tab buttons */}
      <div className="tabbed-metadata-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => toggleTab(tab.id)}
            className={`tab-button ${activeTab === tab.id ? 'tab-active' : ''}`}
            aria-expanded={activeTab === tab.id}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
            {tab.count > 0 && (
              <span className="tab-count">{tab.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        {activeTab && (
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="tab-content"
          >
            {activeTab === 'characters' && (
              <CharactersContent characters={characters} />
            )}
            {activeTab === 'learning' && (
              <LearningContent educationalValue={educationalValue} />
            )}
            {activeTab === 'analysis' && (
              <AnalysisContent analysis={analysis} />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function CharactersContent({ characters }: { characters: CharacterMemory[] }) {
  if (characters.length === 0) {
    return (
      <div className="tab-empty">
        <span>No characters identified in this story</span>
      </div>
    )
  }

  return (
    <div className="characters-grid">
      {characters.map((char, index) => (
        <motion.div
          key={char.character_name}
          className="character-card"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.1 }}
        >
          <div className="character-avatar">
            {char.character_name[0]}
          </div>
          <div className="character-info">
            <span className="character-name">{char.character_name}</span>
            <span className="character-description">{char.description}</span>
          </div>
          {char.appearances > 1 && (
            <span className="character-appearances">
              {char.appearances}x
            </span>
          )}
        </motion.div>
      ))}
    </div>
  )
}

function LearningContent({ educationalValue }: { educationalValue: EducationalValue }) {
  return (
    <div className="learning-content">
      {/* Themes */}
      {educationalValue.themes.length > 0 && (
        <div className="learning-section">
          <h4 className="learning-section-title">
            <span>🎯</span> Themes
          </h4>
          <div className="learning-tags">
            {educationalValue.themes.map((theme) => (
              <span key={theme} className="learning-tag theme-tag">
                {theme}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Concepts */}
      {educationalValue.concepts.length > 0 && (
        <div className="learning-section">
          <h4 className="learning-section-title">
            <span>💡</span> Concepts
          </h4>
          <div className="learning-tags">
            {educationalValue.concepts.map((concept) => (
              <span key={concept} className="learning-tag concept-tag">
                {concept}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Moral */}
      {educationalValue.moral && (
        <div className="learning-section">
          <h4 className="learning-section-title">
            <span>❤️</span> Moral
          </h4>
          <p className="learning-moral">{educationalValue.moral}</p>
        </div>
      )}
    </div>
  )
}

function formatKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function AnalysisValue({ value }: { value: unknown }) {
  if (value == null) return null

  // String
  if (typeof value === 'string') {
    return <span className="analysis-value">{value}</span>
  }

  // Number
  if (typeof value === 'number') {
    return <span className="analysis-value">{value}</span>
  }

  // Array of strings
  if (Array.isArray(value)) {
    const items = value.filter(v => v != null)
    if (items.length === 0) return null

    // Array of primitives → tags
    if (items.every(v => typeof v === 'string' || typeof v === 'number')) {
      return (
        <div className="analysis-tags">
          {items.map((item, i) => (
            <span key={i} className="analysis-tag">{String(item)}</span>
          ))}
        </div>
      )
    }

    // Array of objects → render each
    return (
      <div className="analysis-details">
        {items.map((item, i) => (
          <div key={i} className="analysis-section" style={{ paddingLeft: '0.5rem' }}>
            <AnalysisObject data={item as Record<string, unknown>} />
          </div>
        ))}
      </div>
    )
  }

  // Nested object
  if (typeof value === 'object') {
    return <AnalysisObject data={value as Record<string, unknown>} />
  }

  return <span className="analysis-value">{String(value)}</span>
}

function AnalysisObject({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([, v]) => v != null)
  if (entries.length === 0) return null

  return (
    <div className="analysis-details">
      {entries.map(([key, val]) => (
        <div key={key} className="analysis-row">
          <span className="analysis-label">{formatKey(key)}:</span>
          <AnalysisValue value={val} />
        </div>
      ))}
    </div>
  )
}

function AnalysisContent({ analysis }: { analysis: Record<string, unknown> }) {
  const entries = Object.entries(analysis).filter(([, v]) => v != null)

  if (entries.length === 0) {
    return (
      <div className="tab-empty">
        <span>No detailed analysis available</span>
      </div>
    )
  }

  return (
    <div className="analysis-content">
      {entries.map(([key, value]) => (
        <div key={key} className="analysis-section">
          <h4 className="analysis-section-title">
            <span>🔍</span> {formatKey(key)}
          </h4>
          {typeof value === 'string' || typeof value === 'number' ? (
            <p className="analysis-value" style={{ paddingLeft: '1.5rem' }}>{String(value)}</p>
          ) : (
            <div style={{ paddingLeft: '1.5rem' }}>
              <AnalysisValue value={value} />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default TabbedMetadata
