import apiClient from "../client";
import type {
  StoryVideosResponse,
  VideoJobRequest,
  VideoJobResponse,
  VideoJobStatusResponse,
} from "@/types/api";

export const videoService = {
  async generateVideo(
    request: VideoJobRequest,
  ): Promise<VideoJobResponse> {
    const response = await apiClient.post<VideoJobResponse>(
      "/video/generate",
      request,
    );
    return response.data;
  },

  async getVideoStatus(jobId: string): Promise<VideoJobStatusResponse> {
    const response = await apiClient.get<VideoJobStatusResponse>(
      `/video/status/${jobId}`,
    );
    return response.data;
  },

  async getVideosByStory(storyId: string): Promise<StoryVideosResponse> {
    const response = await apiClient.get<StoryVideosResponse>(
      `/video/story/${storyId}`,
    );
    return response.data;
  },
};

export default videoService;
