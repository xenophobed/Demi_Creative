import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from "../client";
import { videoService } from "./videoService";

const mockedGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;
const mockedPost = apiClient.post as unknown as ReturnType<typeof vi.fn>;

afterEach(() => {
  mockedGet.mockReset();
  mockedPost.mockReset();
});

describe("videoService", () => {
  it("starts story video generation through the video endpoint", async () => {
    const fake = {
      job_id: "job-1",
      story_id: "story-1",
      status: "pending",
      estimated_completion: null,
      created_at: "2026-05-20T00:00:00",
    };
    mockedPost.mockResolvedValueOnce({ data: fake });

    const result = await videoService.generateVideo({
      story_id: "story-1",
      style: "storybook",
      include_audio: true,
      duration_seconds: 10,
    });

    expect(result).toEqual(fake);
    expect(mockedPost).toHaveBeenCalledWith("/video/generate", {
      story_id: "story-1",
      style: "storybook",
      include_audio: true,
      duration_seconds: 10,
    });
  });

  it("checks provider video job status", async () => {
    const fake = {
      job_id: "job-1",
      status: "processing",
      progress_percent: 42,
      video_url: null,
      error_message: null,
      created_at: "2026-05-20T00:00:00",
      completed_at: null,
    };
    mockedGet.mockResolvedValueOnce({ data: fake });

    const result = await videoService.getVideoStatus("job-1");

    expect(result).toEqual(fake);
    expect(mockedGet).toHaveBeenCalledWith("/video/status/job-1");
  });

  it("lists prior videos for a story", async () => {
    const fake = {
      story_id: "story-1",
      total: 1,
      videos: [
        {
          video_id: "job-1",
          status: "completed",
          style: "storybook",
          video_url: "/data/videos/job-1.mp4",
          has_audio: false,
          created_at: "2026-05-20T00:00:00",
        },
      ],
    };
    mockedGet.mockResolvedValueOnce({ data: fake });

    const result = await videoService.getVideosByStory("story-1");

    expect(result).toEqual(fake);
    expect(mockedGet).toHaveBeenCalledWith("/video/story/story-1");
  });
});
