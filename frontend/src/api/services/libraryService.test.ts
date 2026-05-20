import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../client", () => ({
  default: {
    get: vi.fn(),
  },
}));

import apiClient from "../client";
import { libraryService } from "./libraryService";

const mockedGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;

afterEach(() => {
  mockedGet.mockReset();
});

describe("libraryService.getCounts", () => {
  it("loads profile stats from the library-owned counts endpoint", async () => {
    const fake = {
      art_story_count: 2,
      interactive_count: 1,
      news_count: 3,
      total: 6,
    };
    mockedGet.mockResolvedValueOnce({ data: fake });

    const result = await libraryService.getCounts();

    expect(result).toEqual(fake);
    expect(mockedGet).toHaveBeenCalledWith("/library/counts");
  });
});

describe("libraryService.getRichStats", () => {
  it("passes child scope and parent dashboard flag when provided", async () => {
    const fake = {
      periods: [],
      streak_days: 0,
    };
    mockedGet.mockResolvedValueOnce({ data: fake });

    const result = await libraryService.getRichStats("month", {
      childId: "child_alpha",
      parentDashboard: true,
    });

    expect(result).toEqual(fake);
    expect(mockedGet).toHaveBeenCalledWith("/library/stats-rich", {
      params: {
        group_by: "month",
        child_id: "child_alpha",
        parent_dashboard: true,
      },
    });
  });
});
