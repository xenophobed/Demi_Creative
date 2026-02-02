import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { CharacterMemory, EducationalValue } from '@/types/api'

type TabType = 'characters' | 'learning' | 'analysis'

interface DrawingAnalysis {
  drawing_elements?: {
    main_character?: string
    setting?: string
    decorative_elements?: string[]
    text?: string
  }
  story_connection?: Record<string, string>
  age_appropriateness?: string
  interest_alignment?: string
}

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

  const analysisData = analysis as DrawingAnalysis

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
              <AnalysisContent analysis={analysisData} />
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

function AnalysisContent({ analysis }: { analysis: DrawingAnalysis }) {
  if (Object.keys(analysis).length === 0) {
    return (
      <div className="tab-empty">
        <span>No detailed analysis available</span>
      </div>
    )
  }

  return (
    <div className="analysis-content">
      {/* Drawing elements */}
      {analysis.drawing_elements && (
        <div className="analysis-section">
          <h4 className="analysis-section-title">
            <span>🎨</span> Drawing Elements
          </h4>
          <div className="analysis-details">
            {analysis.drawing_elements.main_character && (
              <div className="analysis-row">
                <span className="analysis-label">Main character:</span>
                <span className="analysis-value">{analysis.drawing_elements.main_character}</span>
              </div>
            )}
            {analysis.drawing_elements.setting && (
              <div className="analysis-row">
                <span className="analysis-label">Setting:</span>
                <span className="analysis-value">{analysis.drawing_elements.setting}</span>
              </div>
            )}
            {analysis.drawing_elements.decorative_elements &&
              analysis.drawing_elements.decorative_elements.length > 0 && (
              <div className="analysis-row">
                <span className="analysis-label">Elements:</span>
                <div className="analysis-tags">
                  {analysis.drawing_elements.decorative_elements.map((elem) => (
                    <span key={elem} className="analysis-tag">{elem}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Story connection */}
      {analysis.story_connection && Object.keys(analysis.story_connection).length > 0 && (
        <div className="analysis-section">
          <h4 className="analysis-section-title">
            <span>🔗</span> Story Connection
          </h4>
          <div className="analysis-details">
            {Object.entries(analysis.story_connection).map(([key, value]) => (
              <div key={key} className="analysis-row">
                <span className="analysis-label">{formatKey(key)}:</span>
                <span className="analysis-value">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Age appropriateness */}
      {analysis.age_appropriateness && (
        <div className="analysis-badge success">
          <span>✅</span>
          <span>{analysis.age_appropriateness}</span>
        </div>
      )}

      {/* Interest alignment */}
      {analysis.interest_alignment && (
        <div className="analysis-badge info">
          <span>💫</span>
          <span>{analysis.interest_alignment}</span>
        </div>
      )}
    </div>
  )
}

function formatKey(key: string): string {
  const keyMap: Record<string, string> = {
    bird: 'Bird',
    musical_notes: 'Musical Notes',
    rain: 'Rain',
    flowers: 'Flowers',
    text_integration: 'Text Integration',
  }
  return keyMap[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default TabbedMetadata
