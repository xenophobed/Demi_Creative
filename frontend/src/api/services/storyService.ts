import apiClient from "../client";
import type {
  ImageToStoryResponse,
  InteractiveStoryStartRequest,
  InteractiveStoryStartResponse,
  ChoiceRequest,
  ChoiceResponse,
  SessionStatusResponse,
  SessionResumeResponse,
  HealthCheckResponse,
  AgeGroup,
  StreamCallbacks,
  NewsToKidsRequest,
  NewsToKidsResponse,
  MorningShowRequest,
  MorningShowResponse,
  MorningShowEpisode,
  PaginatedMorningShowResponse,
  SubscriptionRequest,
  SubscriptionResponse,
  SubscriptionListResponse,
  NewsCategory,
  MorningShowTrackRequest,
  MorningShowTrackResponse,
  MorningShowOnDemandRequest,
} from "@/types/api";
import { consumeSSEStream } from "../utils/sseStream";
import { getFreshAuthHeaders } from "../authUtils";

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

/**
 * Story service API
 */
export const storyService = {
  /**
   * Generate story from drawing
   * @param image Image file
   * @param params Request parameters
   */
  async generateStoryFromImage(
    image: File,
    params: {
      childId: string;
      ageGroup: AgeGroup;
      interests?: string[];
      voice?: string;
      enableAudio?: boolean;
      artTheme?: string;
      provider?: string;
    },
  ): Promise<ImageToStoryResponse> {
    const formData = new FormData();
    formData.append("image", image);
    formData.append("child_id", params.childId);
    formData.append("age_group", params.ageGroup);

    if (params.interests && params.interests.length > 0) {
      formData.append("interests", params.interests.join(","));
    }
    if (params.voice) {
      formData.append("voice", params.voice);
    }
    if (params.enableAudio !== undefined) {
      formData.append("enable_audio", String(params.enableAudio));
    }
    if (params.artTheme && params.artTheme !== "none") {
      formData.append("art_theme", params.artTheme);
    }
    if (params.provider) {
      formData.append("provider", params.provider);
    }

    const response = await apiClient.post<ImageToStoryResponse>(
      "/image-to-story",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        timeout: 120000, // 2 minutes for image processing + story generation
      },
    );

    return response.data;
  },

  /**
   * Generate story from drawing (streaming)
   * Uses Server-Sent Events for real-time progress
   */
  async generateStoryFromImageStream(
    image: File,
    params: {
      childId: string;
      ageGroup: AgeGroup;
      interests?: string[];
      voice?: string;
      enableAudio?: boolean;
      artTheme?: string;
      provider?: string;
    },
    callbacks: StreamCallbacks,
    signal?: AbortSignal,
  ): Promise<void> {
    const formData = new FormData();
    formData.append("image", image);
    formData.append("child_id", params.childId);
    formData.append("age_group", params.ageGroup);

    if (params.interests && params.interests.length > 0) {
      formData.append("interests", params.interests.join(","));
    }
    if (params.voice) {
      formData.append("voice", params.voice);
    }
    if (params.enableAudio !== undefined) {
      formData.append("enable_audio", String(params.enableAudio));
    }
    if (params.artTheme && params.artTheme !== "none") {
      formData.append("art_theme", params.artTheme);
    }
    if (params.provider) {
      formData.append("provider", params.provider);
    }

    const response = await fetch(`${API_BASE_URL}/image-to-story/stream`, {
      method: "POST",
      headers: await getFreshAuthHeaders(),
      body: formData,
      signal,
    });

    if (!response.ok) {
      if (response.status === 429) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData.detail ?? errorData;
        const resetsAt = detail.resets_at;
        let friendlyMsg = "You've reached your daily creation limit!";
        if (resetsAt) {
          const resetDate = new Date(resetsAt);
          const hours = resetDate.getHours().toString().padStart(2, "0");
          const minutes = resetDate.getMinutes().toString().padStart(2, "0");
          friendlyMsg += ` You can create again tomorrow at ${hours}:${minutes}.`;
        } else {
          friendlyMsg += " Come back tomorrow to draw new stories!";
        }
        throw new Error(friendlyMsg);
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    await consumeSSEStream(response, callbacks);
  },

  /**
   * Start interactive story
   */
  async startInteractiveStory(
    params: InteractiveStoryStartRequest,
  ): Promise<InteractiveStoryStartResponse> {
    const response = await apiClient.post<InteractiveStoryStartResponse>(
      "/story/interactive/start",
      params,
    );
    return response.data;
  },

  /**
   * Make a choice in interactive story
   */
  async makeChoice(
    sessionId: string,
    choice: ChoiceRequest,
  ): Promise<ChoiceResponse> {
    const response = await apiClient.post<ChoiceResponse>(
      `/story/interactive/${sessionId}/choose`,
      choice,
    );
    return response.data;
  },

  /**
   * Get session status
   */
  async getSessionStatus(sessionId: string): Promise<SessionStatusResponse> {
    const response = await apiClient.get<SessionStatusResponse>(
      `/story/interactive/${sessionId}/status`,
    );
    return response.data;
  },

  /**
   * Resume an interactive story session (fetch full segment data)
   */
  async resumeSession(sessionId: string): Promise<SessionResumeResponse> {
    const response = await apiClient.get<SessionResumeResponse>(
      `/story/interactive/${sessionId}/resume`,
    );
    return response.data;
  },

  /**
   * Get story details
   */
  async getStory(storyId: string): Promise<ImageToStoryResponse> {
    const response = await apiClient.get<ImageToStoryResponse>(
      `/stories/${storyId}`,
    );
    return response.data;
  },

  /**
   * Get story history list
   */
  async getStoryHistory(childId: string): Promise<ImageToStoryResponse[]> {
    const response = await apiClient.get<ImageToStoryResponse[]>(
      `/stories/history/${childId}`,
    );
    return response.data;
  },

  /**
   * Save interactive story to My Library
   */
  async saveInteractiveStory(
    sessionId: string,
  ): Promise<{ story_id: string; session_id: string; message: string }> {
    const response = await apiClient.post(
      `/story/interactive/${sessionId}/save`,
    );
    return response.data;
  },

  /**
   * Delete a story (art story or news conversion)
   */
  async deleteStory(storyId: string): Promise<void> {
    await apiClient.delete(`/stories/${storyId}`);
  },

  /**
   * Delete an interactive story session
   */
  async deleteSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/story/interactive/${sessionId}`);
  },

  /**
   * Health check
   */
  async healthCheck(): Promise<HealthCheckResponse> {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json() as Promise<HealthCheckResponse>;
  },

  /**
   * Start interactive story (streaming)
   * Uses Server-Sent Events for real-time progress
   */
  async startInteractiveStoryStream(
    params: InteractiveStoryStartRequest,
    callbacks: StreamCallbacks,
    signal?: AbortSignal,
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/story/interactive/start/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(await getFreshAuthHeaders()),
        },
        body: JSON.stringify(params),
        signal,
      },
    );

    if (!response.ok) {
      if (response.status === 429) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData.detail ?? errorData;
        const resetsAt = detail.resets_at;
        let friendlyMsg = "You've reached your daily creation limit!";
        if (resetsAt) {
          const resetDate = new Date(resetsAt);
          const hours = resetDate.getHours().toString().padStart(2, "0");
          const minutes = resetDate.getMinutes().toString().padStart(2, "0");
          friendlyMsg += ` You can create again tomorrow at ${hours}:${minutes}.`;
        } else {
          friendlyMsg += " Come back tomorrow to draw new stories!";
        }
        throw new Error(friendlyMsg);
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    await consumeSSEStream(response, callbacks);
  },

  /**
   * Convert news article to kid-friendly content
   */
  async convertNews(params: NewsToKidsRequest): Promise<NewsToKidsResponse> {
    const response = await apiClient.post<NewsToKidsResponse>(
      "/kids-daily/convert",
      params,
    );
    return response.data;
  },

  /**
   * Convert news to kids (streaming)
   */
  async convertNewsStream(
    params: NewsToKidsRequest,
    callbacks: StreamCallbacks,
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/kids-daily/convert/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(await getFreshAuthHeaders()),
      },
      body: JSON.stringify(params),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    await consumeSSEStream(response, callbacks);
  },

  /**
   * Get news conversion history
   */
  async getNewsHistory(childId: string): Promise<NewsToKidsResponse[]> {
    const response = await apiClient.get<{ items: NewsToKidsResponse[] }>(
      `/kids-daily/history/${childId}`,
    );
    // Backend returns paginated response { items, total, limit, offset }
    return (
      response.data.items ?? (response.data as unknown as NewsToKidsResponse[])
    );
  },

  /**
   * Generate Kids Daily episode
   */
  async generateMorningShow(
    params: MorningShowRequest,
  ): Promise<MorningShowResponse> {
    const response = await apiClient.post<MorningShowResponse>(
      "/kids-daily/generate",
      params,
    );
    return response.data;
  },

  /**
   * Generate Kids Daily episode (streaming)
   */
  async generateMorningShowStream(
    params: MorningShowRequest,
    callbacks: StreamCallbacks,
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/kids-daily/generate/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(await getFreshAuthHeaders()),
      },
      body: JSON.stringify(params),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    await consumeSSEStream(response, callbacks);
  },

  /**
   * Get Kids Daily episode details
   */
  async getMorningShowEpisode(episodeId: string): Promise<MorningShowEpisode> {
    const response = await apiClient.get<MorningShowEpisode>(
      `/kids-daily/episode/${episodeId}`,
    );
    return response.data;
  },

  /**
   * List Kids Daily episodes by child
   */
  async listMorningShowEpisodes(
    childId: string,
    params?: { limit?: number; offset?: number },
  ): Promise<PaginatedMorningShowResponse> {
    const response = await apiClient.get<PaginatedMorningShowResponse>(
      `/kids-daily/episodes/${childId}`,
      { params },
    );
    return response.data;
  },

  /**
   * Subscribe to topic channel
   */
  async subscribeTopic(
    request: SubscriptionRequest,
  ): Promise<SubscriptionResponse> {
    const response = await apiClient.post<SubscriptionResponse>(
      "/subscriptions",
      request,
    );
    return response.data;
  },

  /**
   * Unsubscribe from topic channel
   */
  async unsubscribeTopic(childId: string, topic: NewsCategory): Promise<void> {
    await apiClient.delete(`/subscriptions/${childId}/${topic}`);
  },

  /**
   * List active topic subscriptions
   */
  async getSubscriptions(childId: string): Promise<SubscriptionListResponse> {
    const response = await apiClient.get<SubscriptionListResponse>(
      `/subscriptions/${childId}`,
    );
    return response.data;
  },

  /**
   * Generate Kids Daily episode on-demand (instant)
   */
  async generateMorningShowOnDemand(
    params: MorningShowOnDemandRequest,
    signal?: AbortSignal,
  ): Promise<MorningShowResponse> {
    const response = await apiClient.post<MorningShowResponse>(
      "/kids-daily/generate-now",
      params,
      { signal },
    );
    return response.data;
  },

  /**
   * Generate Kids Daily episode on-demand (streaming)
   */
  async generateMorningShowOnDemandStream(
    params: MorningShowOnDemandRequest,
    callbacks: StreamCallbacks,
    signal?: AbortSignal,
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/kids-daily/generate-now/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(await getFreshAuthHeaders()),
        },
        body: JSON.stringify(params),
        signal,
      },
    );

    if (!response.ok) {
      if (response.status === 429) {
        const errorData = await response.json();
        throw Object.assign(
          new Error(
            errorData.message ||
              errorData.detail ||
              "Too many Kids Daily listens right now.",
          ),
          {
            status: 429,
            retry_after: errorData.retry_after || 60,
          },
        );
      }
      if (response.status === 400) {
        const errorData = await response.json();
        throw Object.assign(
          new Error(errorData.detail || "Subscription required or invalid request."),
          {
            status: 400,
          },
        );
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    await consumeSSEStream(response, callbacks);
  },

  /**
   * Track Kids Daily playback event
   */
  async trackMorningShowEvent(
    request: MorningShowTrackRequest,
  ): Promise<MorningShowTrackResponse> {
    const response = await apiClient.post<MorningShowTrackResponse>(
      "/kids-daily/track",
      request,
    );
    return response.data;
  },

  /**
   * Make a choice in interactive story (streaming)
   */
  async makeChoiceStream(
    sessionId: string,
    choice: ChoiceRequest,
    callbacks: StreamCallbacks,
    signal?: AbortSignal,
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/story/interactive/${sessionId}/choose/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(await getFreshAuthHeaders()),
        },
        body: JSON.stringify(choice),
        signal,
      },
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    await consumeSSEStream(response, callbacks);
  },

  /**
   * End an unlimited-mode interactive story (streaming) (#331)
   */
  async endStoryStream(
    sessionId: string,
    callbacks: StreamCallbacks,
    signal?: AbortSignal,
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/story/interactive/${sessionId}/end/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(await getFreshAuthHeaders()),
        },
        signal,
      },
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    await consumeSSEStream(response, callbacks);
  },

  /**
   * Generate audio on-demand for an interactive story segment (9-12 age group)
   */
  async generateAudioOnDemand(
    sessionId: string,
    segmentId: number,
    voice?: string,
    speed?: number,
  ): Promise<{
    session_id: string;
    segment_id: number;
    audio_url: string;
    duration?: number;
  }> {
    const response = await apiClient.post("/audio/generate", {
      session_id: sessionId,
      segment_id: segmentId,
      voice: voice || "alloy",
      speed: speed || 1.1,
    });
    return response.data;
  },

  /**
   * Generate audio on-demand for an image-to-story (9-12 age group)
   */
  async generateAudioForStory(
    storyId: string,
    voice?: string,
    speed?: number,
  ): Promise<{ story_id: string; audio_url: string; duration?: number }> {
    const response = await apiClient.post("/audio/generate-for-story", {
      story_id: storyId,
      voice: voice || "alloy",
      speed: speed || 1.1,
    });
    return response.data;
  },
  /**
   * Preview a TTS voice — returns a short audio sample URL (#333)
   */
  async previewVoice(
    voiceId: string,
    provider: string,
  ): Promise<{ voice_id: string; provider: string; audio_url: string; cached: boolean }> {
    const response = await apiClient.get("/audio/preview", {
      params: { voice_id: voiceId, provider },
    });
    return response.data;
  },

  /** Get a saved news conversion by ID (#181) */
  async getNewsConversion(conversionId: string): Promise<NewsToKidsResponse> {
    const response = await apiClient.get(
      `/kids-daily/conversion/${conversionId}`,
    );
    return response.data;
  },
};

export default storyService;
