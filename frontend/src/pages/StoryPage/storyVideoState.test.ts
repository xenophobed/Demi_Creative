/* @vitest-environment node */

import { describe, expect, it } from "vitest";
import {
  applyProviderStatusToStoryVideo,
  findLatestCompletedStoryVideoUrl,
  getStoryVideoStatusMessage,
  shouldRenderPictureBookFallback,
} from ".";

describe("story video state helpers", () => {
  it("maps provider statuses to child-facing UI states", () => {
    expect(applyProviderStatusToStoryVideo("pending")).toBe("queued");
    expect(applyProviderStatusToStoryVideo("processing")).toBe("generating");
    expect(applyProviderStatusToStoryVideo("completed")).toBe("completed");
    expect(applyProviderStatusToStoryVideo("failed")).toBe("failed");
  });

  it("automatically renders the picture-book fallback when video fails", () => {
    expect(shouldRenderPictureBookFallback(false, "failed")).toBe(true);
    expect(shouldRenderPictureBookFallback(false, "idle")).toBe(false);
    expect(shouldRenderPictureBookFallback(true, "completed")).toBe(true);
  });

  it("uses recoverable copy for failed provider states", () => {
    expect(getStoryVideoStatusMessage("failed")).toBe(
      "Video is not available right now",
    );
  });

  it("hydrates the newest completed story video URL for owner-visible playback", () => {
    const url = findLatestCompletedStoryVideoUrl({
      story_id: "story-1",
      total: 3,
      videos: [
        {
          video_id: "pending-1",
          status: "processing",
          video_url: null,
          has_audio: false,
          created_at: "2026-05-20T10:00:00",
        },
        {
          video_id: "done-new",
          status: "completed",
          video_url: "/data/videos/new.mp4",
          has_audio: true,
          created_at: "2026-05-20T11:00:00",
        },
        {
          video_id: "done-old",
          status: "completed",
          video_url: "/data/videos/old.mp4",
          has_audio: false,
          created_at: "2026-05-20T09:00:00",
        },
      ],
    });

    expect(url).toBe("/data/videos/new.mp4");
  });
});
