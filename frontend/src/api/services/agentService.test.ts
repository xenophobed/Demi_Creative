/**
 * Logic-only tests for agentService. Mocks apiClient and exercises
 * just the 404 -> null contract; full request shape is asserted
 * implicitly by the params we hand to the mocked client.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { AxiosError } from "axios";

vi.mock("../client", () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

import apiClient from "../client";
import { getAgent, putAgent } from "./agentService";

const mockedGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;
const mockedPut = apiClient.put as unknown as ReturnType<typeof vi.fn>;

afterEach(() => {
  mockedGet.mockReset();
  mockedPut.mockReset();
});

describe("getAgent", () => {
  it("returns the Agent on 200", async () => {
    const fake = {
      agent_id: "agt_abc",
      user_id: "u1",
      child_id: "c1",
      agent_name: "Sparkle",
      agent_avatar_id: "emoji:🦊",
      agent_title: "Story Wizard",
      created_at: "2026-01-01T00:00:00",
      updated_at: "2026-01-01T00:00:00",
    };
    mockedGet.mockResolvedValueOnce({ data: fake });
    const result = await getAgent("c1");
    expect(result).toEqual(fake);
    expect(mockedGet).toHaveBeenCalledWith(
      "/me/agent",
      expect.objectContaining({ params: { child_id: "c1" } }),
    );
  });

  it("resolves to null on 404", async () => {
    const err = new AxiosError("not found");
    // @ts-expect-error -- attaching minimal AxiosResponse for the test
    err.response = { status: 404, data: { detail: { code: "AGENT_NOT_FOUND" } } };
    mockedGet.mockRejectedValueOnce(err);
    const result = await getAgent("missing");
    expect(result).toBeNull();
  });

  it("rethrows on non-404 errors", async () => {
    const err = new AxiosError("server error");
    // @ts-expect-error -- attaching minimal AxiosResponse for the test
    err.response = { status: 500, data: {} };
    mockedGet.mockRejectedValueOnce(err);
    await expect(getAgent("c1")).rejects.toBe(err);
  });
});

describe("putAgent", () => {
  it("returns the upserted Agent", async () => {
    const fake = {
      agent_id: "agt_xyz",
      user_id: "u1",
      child_id: "c1",
      agent_name: "Sparkle",
      agent_avatar_id: "emoji:🦊",
      agent_title: "Story Wizard",
      created_at: "2026-01-01T00:00:00",
      updated_at: "2026-01-02T00:00:00",
    };
    mockedPut.mockResolvedValueOnce({ data: fake });
    const result = await putAgent({
      agent_name: "Sparkle",
      agent_avatar_id: "emoji:🦊",
      agent_title: "Story Wizard",
      child_id: "c1",
    });
    expect(result).toEqual(fake);
    expect(mockedPut).toHaveBeenCalledWith(
      "/me/agent",
      expect.objectContaining({ child_id: "c1" }),
    );
  });
});
