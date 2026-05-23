/* @vitest-environment node */

import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "../client";
import { childProfileService } from "./childProfileService";

vi.mock("../client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

describe("childProfileService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists child profiles", async () => {
    const response = { items: [] };
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: response });

    await expect(childProfileService.list()).resolves.toBe(response);
    expect(apiClient.get).toHaveBeenCalledWith("/child-profiles");
  });

  it("creates a child profile", async () => {
    const profile = {
      child_id: "child-1",
      name: "Milo",
      age_group: "6-8" as const,
      interests: ["Space"],
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: profile });

    await expect(
      childProfileService.create({
        name: "Milo",
        age_group: "6-8",
        interests: ["Space"],
      }),
    ).resolves.toBe(profile);
    expect(apiClient.post).toHaveBeenCalledWith("/child-profiles", {
      name: "Milo",
      age_group: "6-8",
      interests: ["Space"],
    });
  });

  it("updates, defaults, and archives encoded child ids", async () => {
    const profile = {
      child_id: "child alpha",
      name: "Milo",
      age_group: "6-8" as const,
      interests: [],
    };
    vi.mocked(apiClient.patch).mockResolvedValueOnce({ data: profile });
    vi.mocked(apiClient.post)
      .mockResolvedValueOnce({ data: profile })
      .mockResolvedValueOnce({ data: profile });

    await childProfileService.update("child alpha", { name: "Milo" });
    await childProfileService.setDefault("child alpha");
    await childProfileService.archive("child alpha");

    expect(apiClient.patch).toHaveBeenCalledWith(
      "/child-profiles/child%20alpha",
      { name: "Milo" },
    );
    expect(apiClient.post).toHaveBeenNthCalledWith(
      1,
      "/child-profiles/child%20alpha/default",
    );
    expect(apiClient.post).toHaveBeenNthCalledWith(
      2,
      "/child-profiles/child%20alpha/archive",
    );
  });
});
