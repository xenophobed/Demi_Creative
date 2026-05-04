/**
 * Logic-only tests for hubService — mocks apiClient and exercises the
 * URL shape + payload contract for the group + post wrappers.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { AxiosError } from "axios";

vi.mock("../client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from "../client";
import {
  createGroup,
  createHubPost,
  getGroup,
  joinGroup,
  listGroupPosts,
  listGroups,
} from "./hubService";

const mockedGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;
const mockedPost = apiClient.post as unknown as ReturnType<typeof vi.fn>;

afterEach(() => {
  mockedGet.mockReset();
  mockedPost.mockReset();
});

describe("listGroups", () => {
  it("hits /hub/groups and returns the list payload", async () => {
    const fake = { items: [], total: 0 };
    mockedGet.mockResolvedValueOnce({ data: fake });
    const r = await listGroups();
    expect(r).toEqual(fake);
    expect(mockedGet).toHaveBeenCalledWith("/hub/groups");
  });
});

describe("createGroup", () => {
  it("posts the create payload to /hub/groups", async () => {
    const fake = {
      group_id: "g1",
      slug: "dragons",
      name: "Dragons",
      description: null,
      theme: null,
      visibility: "public",
      invite_token: null,
      created_at: "2026-01-01T00:00:00",
      member_count: 1,
    };
    mockedPost.mockResolvedValueOnce({ data: fake });
    const r = await createGroup({ name: "Dragons", visibility: "public" });
    expect(r).toEqual(fake);
    expect(mockedPost).toHaveBeenCalledWith(
      "/hub/groups",
      { name: "Dragons", visibility: "public" },
    );
  });
});

describe("getGroup", () => {
  it("returns null on 404", async () => {
    const err = new AxiosError("nope");
    // @ts-expect-error -- minimal AxiosResponse for the test
    err.response = { status: 404 };
    mockedGet.mockRejectedValueOnce(err);
    const r = await getGroup("missing");
    expect(r).toBeNull();
  });

  it("returns the group on 200", async () => {
    const fake = { group_id: "g2" };
    mockedGet.mockResolvedValueOnce({ data: fake });
    const r = await getGroup("g2");
    expect(r).toEqual(fake);
    expect(mockedGet).toHaveBeenCalledWith("/hub/groups/g2");
  });
});

describe("joinGroup", () => {
  it("includes invite token in query when provided", async () => {
    mockedPost.mockResolvedValueOnce({
      data: { group_id: "g3", role: "member", joined_at: "x" },
    });
    await joinGroup("g3", "TOKEN_123");
    expect(mockedPost).toHaveBeenCalledWith(
      "/hub/groups/g3/join",
      null,
      { params: { invite: "TOKEN_123" } },
    );
  });

  it("omits params when no token", async () => {
    mockedPost.mockResolvedValueOnce({
      data: { group_id: "g4", role: "member", joined_at: "x" },
    });
    await joinGroup("g4");
    expect(mockedPost).toHaveBeenCalledWith(
      "/hub/groups/g4/join",
      null,
      undefined,
    );
  });
});

describe("listGroupPosts", () => {
  it("threads cursor params into the GET", async () => {
    mockedGet.mockResolvedValueOnce({ data: { items: [], next_cursor: null } });
    await listGroupPosts("g5", {
      limit: 5,
      cursor: { cursor_created_at: "2026-01-01", cursor_post_id: "p1" },
    });
    expect(mockedGet).toHaveBeenCalledWith(
      "/hub/groups/g5/posts",
      {
        params: {
          limit: 5,
          cursor_created_at: "2026-01-01",
          cursor_post_id: "p1",
        },
      },
    );
  });
});

describe("createHubPost", () => {
  it("posts the body to the group's /posts path", async () => {
    mockedPost.mockResolvedValueOnce({
      data: {
        post_id: "p2",
        group_id: "g6",
        agent_name: "S",
        agent_avatar_id: "emoji:🦁",
        agent_title: "T",
        source_artifact_type: "art_story",
        source_id: "s",
        caption: null,
        created_at: "x",
      },
    });
    await createHubPost("g6", {
      source_artifact_type: "art_story",
      source_id: "s",
    });
    expect(mockedPost).toHaveBeenCalledWith(
      "/hub/groups/g6/posts",
      { source_artifact_type: "art_story", source_id: "s" },
    );
  });
});
