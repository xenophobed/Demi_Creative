import { describe, expect, it, vi, beforeEach } from "vitest";
import apiClient from "../client";
import { achievementService } from "./achievementService";

vi.mock("../client", () => ({
  default: {
    get: vi.fn(),
  },
}));

describe("achievementService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches badges for an encoded child id", async () => {
    const response = {
      child_id: "child alpha",
      items: [],
      total: 0,
      available_definitions: [],
    };
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: response });

    await expect(achievementService.getForChild("child alpha")).resolves.toBe(
      response,
    );
    expect(apiClient.get).toHaveBeenCalledWith(
      "/achievements/child%20alpha",
    );
  });
});
