export type AgeGroupKey = '3-5' | '6-8' | '9-12'

export interface AgeLayoutConfig {
  gridCols: number
  gridClass: string
  cardSize: 'sm' | 'md' | 'lg'
  fontSize: string
  showWordCount: boolean
  showSearchBar: boolean
  showGrowthTimeline: boolean
}

const AGE_CONFIGS: Record<string, AgeLayoutConfig> = {
  '3-5': {
    gridCols: 2,
    gridClass: 'grid-cols-1 sm:grid-cols-2',
    cardSize: 'lg',
    fontSize: 'text-lg',
    showWordCount: false,
    showSearchBar: false,
    showGrowthTimeline: false,
  },
  '6-8': {
    gridCols: 3,
    gridClass: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    cardSize: 'md',
    fontSize: 'text-base',
    showWordCount: true,
    showSearchBar: true,
    showGrowthTimeline: false,
  },
  '9-12': {
    gridCols: 4,
    gridClass: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
    cardSize: 'sm',
    fontSize: 'text-sm',
    showWordCount: true,
    showSearchBar: true,
    showGrowthTimeline: true,
  },
}

const DEFAULT_CONFIG = AGE_CONFIGS['6-8']

export function getAgeLayoutConfig(ageGroup?: string | null): AgeLayoutConfig {
  if (!ageGroup) return DEFAULT_CONFIG
  return AGE_CONFIGS[ageGroup] ?? DEFAULT_CONFIG
}
