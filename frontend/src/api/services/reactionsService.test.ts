/**
 * Logic-only tests for reactionsService — mocks apiClient and exercises
 * the (postId, reaction_type) shape sent to the server and the
 * canonical ReactionState returned.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from "../client";
import { getReactions, toggleReaction } from "./reactionsService";

const mockedGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;
const mockedPost = apiClient.post as unknown as ReturnType<typeof vi.fn>;

afterEach(() => {
  mockedGet.mockReset();
  mockedPost.mockReset();
});

describe("toggleReaction", () => {
  it("posts the right body and returns the canonical state", async () => {
    const fake = {
      post_id: "p1",
      reaction_type: "heart",
      active: true,
      counts: { heart: 1, star: 0, wow: 0 },
      viewer_reactions: ["heart"],
    };
    mockedPost.mockResolvedValueOnce({ data: fake });
    const result = await toggleReaction("p1", "heart");
    expect(result).toEqual(fake);
    expect(mockedPost).toHaveBeenCalledWith(
      "/hub/posts/p1/reactions",
      { reaction_type: "heart" },
    );
  });
});

describe("getReactions", () => {
  it("returns the ReactionState payload", async () => {
    const fake = {
      post_id: "p2",
      counts: { heart: 3, star: 1, wow: 0 },
      viewer_reactions: ["heart"],
    };
    mockedGet.mockResolvedValueOnce({ data: fake });
    const result = await getReactions("p2");
    expect(result).toEqual(fake);
    expect(mockedGet).toHaveBeenCalledWith("/hub/posts/p2/reactions");
  });
});
