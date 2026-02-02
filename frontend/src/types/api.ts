/**
 * API Types - 与后端 Pydantic 模型对应
 */

// 枚举类型
export type AgeGroup = '3-5' | '6-9' | '10-12';

export type VoiceType = 'nova' | 'shimmer' | 'alloy' | 'echo' | 'fable' | 'onyx';

export type StoryMode = 'linear' | 'interactive';

export type SessionStatus = 'active' | 'completed' | 'expired';

// 画作转故事请求
export interface ImageToStoryRequest {
  child_id: string;
  age_group: AgeGroup;
  interests?: string[];
  voice?: VoiceType;
  enable_audio?: boolean;
}

// 故事内容
export interface StoryContent {
  text: string;
  word_count: number;
  age_adapted: boolean;
}

// 教育价值
export interface EducationalValue {
  themes: string[];
  concepts: string[];
  moral?: string;
}

// 角色记忆
export interface CharacterMemory {
  character_name: string;
  description: string;
  appearances: number;
}

// 画作转故事响应
export interface ImageToStoryResponse {
  story_id: string;
  story: StoryContent;
  image_url: string | null;
  audio_url: string | null;
  educational_value: EducationalValue;
  characters: CharacterMemory[];
  analysis: Record<string, unknown>;
  safety_score: number;
  created_at: string;
}

// 互动故事请求
export interface InteractiveStoryStartRequest {
  child_id: string;
  age_group: AgeGroup;
  interests: string[];
  theme?: string;
  voice?: VoiceType;
  enable_audio?: boolean;
}

// 故事选项
export interface StoryChoice {
  choice_id: string;
  text: string;
  emoji: string;
}

// 故事段落
export interface StorySegment {
  segment_id: number;
  text: string;
  audio_url: string | null;
  choices: StoryChoice[];
  is_ending: boolean;
}

// 开始互动故事响应
export interface InteractiveStoryStartResponse {
  session_id: string;
  story_title: string;
  opening: StorySegment;
  created_at: string;
}

// 选择分支请求
export interface ChoiceRequest {
  choice_id: string;
}

// 选择分支响应
export interface ChoiceResponse {
  session_id: string;
  next_segment: StorySegment;
  choice_history: string[];
  progress: number;
}

// 会话状态响应
export interface SessionStatusResponse {
  session_id: string;
  status: SessionStatus;
  child_id: string;
  story_title: string;
  current_segment: number;
  total_segments: number;
  choice_history: string[];
  educational_summary: EducationalValue | null;
  created_at: string;
  updated_at: string;
  expires_at: string;
}

// 错误详情
export interface ErrorDetail {
  field?: string;
  message: string;
  code?: string;
}

// 错误响应
export interface ErrorResponse {
  error: string;
  message: string;
  details?: ErrorDetail[];
  timestamp: string;
}

// 健康检查响应
export interface HealthCheckResponse {
  status: string;
  version: string;
  timestamp: string;
  services: Record<string, string>;
}

// 前端专用类型

// 故事历史项
export interface StoryHistoryItem {
  story_id: string;
  title: string;
  preview: string;
  thumbnail_url?: string;
  created_at: string;
  age_group: AgeGroup;
  safety_score: number;
}

// 儿童配置
export interface ChildProfile {
  child_id: string;
  name: string;
  age_group: AgeGroup;
  interests: string[];
  avatar?: string;
}

// 上传状态
export type UploadStatus = 'idle' | 'uploading' | 'processing' | 'success' | 'error';

// 音频播放状态
export interface AudioState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  isLoading: boolean;
}

// ============================================================================
// 流式响应类型
// ============================================================================

// SSE 事件类型
export type SSEEventType =
  | 'status'
  | 'thinking'
  | 'tool_use'
  | 'tool_result'
  | 'session'
  | 'result'
  | 'complete'
  | 'error';

// SSE 事件数据
export interface SSEStatusData {
  status: 'started' | 'processing' | 'completed';
  message: string;
  is_ending?: boolean;
}

export interface SSEThinkingData {
  content: string;
  turn: number;
}

export interface SSEToolUseData {
  tool: string;
  message: string;
}

export interface SSEToolResultData {
  status: string;
  message?: string;
}

export interface SSESessionData {
  session_id: string;
  story_title: string;
}

export interface SSEErrorData {
  error: string;
  message: string;
}

// 流式回调类型
export interface StreamCallbacks {
  onStatus?: (data: SSEStatusData) => void;
  onThinking?: (data: SSEThinkingData) => void;
  onToolUse?: (data: SSEToolUseData) => void;
  onToolResult?: (data: SSEToolResultData) => void;
  onSession?: (data: SSESessionData) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onResult?: (data: any) => void;
  onComplete?: (data: SSEStatusData) => void;
  onError?: (data: SSEErrorData) => void;
}
