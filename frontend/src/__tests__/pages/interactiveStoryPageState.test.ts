import { describe, expect, it } from "vitest";

import { getInteractiveStoryPageState } from "@/pages/InteractiveStoryPage/pageState";

describe("getInteractiveStoryPageState", () => {
  it("keeps the page in resuming mode while session data is loading", () => {
    expect(
      getInteractiveStoryPageState({
        isResuming: true,
        isCompleted: false,
        hasCurrentSegment: false,
      }),
    ).toBe("resuming");
  });

  it("switches to playing once a segment is available", () => {
    expect(
      getInteractiveStoryPageState({
        isResuming: false,
        isCompleted: false,
        hasCurrentSegment: true,
      }),
    ).toBe("playing");
  });
});
