/**
 * streamAgentChat contract tests (#510).
 *
 * Pins the wire protocol between MyAgentPage's chat surface and
 * POST /api/v1/me/agent/chat/stream:
 *   - JSON body when no image is attached.
 *   - multipart/form-data body when an image is attached.
 *   - Routes streamed SSE events (`session`, `thinking`, `launch_flow`,
 *     `result`, `complete`, `error`) to the matching `StreamCallbacks`
 *     entries in order.
 *   - Throws on non-2xx response.
 *
 * We mock global.fetch with a stream-backed Response so the test
 * exercises the real `consumeSSEStream` parser — the chat panel
 * depends on event ordering, not just the HTTP shape.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/authUtils", () => ({
  getFreshAuthHeaders: vi.fn(async () => ({ Authorization: "Bearer test" })),
}));

import { streamAgentChat } from "@/api/services/agentService";
import type { StreamCallbacks } from "@/types/api";

function sseResponse(body: string, init?: { status?: number }): Response {
  return {
    ok: (init?.status ?? 200) < 400,
    status: init?.status ?? 200,
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(body));
        controller.close();
      },
    }),
  } as unknown as Response;
}

describe("streamAgentChat", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a JSON body and Content-Type when no image is attached", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(""));

    await streamAgentChat(
      { child_id: "c1", message: "hi", session_id: null },
      {},
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/me/agent/chat/stream");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.headers.Authorization).toBe("Bearer test");
    const parsed = JSON.parse(init.body as string);
    expect(parsed).toEqual({ child_id: "c1", message: "hi" });
  });

  it("forwards session_id when present so the proxy can resume the SDK session", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(""));

    await streamAgentChat(
      { child_id: "c1", message: "more", session_id: "sess_42" },
      {},
    );

    const init = fetchMock.mock.calls[0][1];
    const parsed = JSON.parse(init.body as string);
    expect(parsed.session_id).toBe("sess_42");
  });

  it("sends multipart FormData (no JSON Content-Type) when an image is attached", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(""));
    const image = new File(["x"], "drawing.png", { type: "image/png" });

    await streamAgentChat(
      { child_id: "c1", message: "look", session_id: null, image },
      {},
    );

    const init = fetchMock.mock.calls[0][1];
    expect(init.body).toBeInstanceOf(FormData);
    // FormData must NOT carry a manual JSON Content-Type — the browser
    // sets the multipart boundary itself.
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
    const form = init.body as FormData;
    expect(form.get("child_id")).toBe("c1");
    expect(form.get("message")).toBe("look");
    expect(form.get("image")).toBeInstanceOf(File);
  });

  it("routes SSE events to their matching callbacks in the order received", async () => {
    const body = [
      'event: session\ndata: {"session_id":"sess_1","story_title":"My Agent Chat"}\n\n',
      'event: status\ndata: {"status":"started","message":"thinking..."}\n\n',
      'event: thinking\ndata: {"content":"Hi ","turn":1}\n\n',
      'event: thinking\ndata: {"content":"there!","turn":1}\n\n',
      'event: launch_flow\ndata: {"flow_type":"image_story","route":"/story/s1","prefill":{"story_id":"s1"}}\n\n',
      'event: result\ndata: {"response_type":"image_story","message":"All done!","session_id":"sess_1"}\n\n',
      'event: complete\ndata: {"status":"completed","message":"Buddy replied."}\n\n',
    ].join("");
    fetchMock.mockResolvedValueOnce(sseResponse(body));

    const order: string[] = [];
    const callbacks: StreamCallbacks = {
      onSession: (d) => order.push(`session:${d.session_id}`),
      onStatus: () => order.push("status"),
      onThinking: (d) => order.push(`thinking:${d.content}`),
      onLaunchFlow: (d) => order.push(`launch_flow:${d.flow_type}`),
      onResult: (d) => order.push(`result:${(d as { message: string }).message}`),
      onComplete: () => order.push("complete"),
    };

    await streamAgentChat({ child_id: "c1", message: "hi" }, callbacks);

    expect(order).toEqual([
      "session:sess_1",
      "status",
      "thinking:Hi ",
      "thinking:there!",
      "launch_flow:image_story",
      "result:All done!",
      "complete",
    ]);
  });

  it("throws when the server responds non-OK so the page surfaces an inline error", async () => {
    fetchMock.mockResolvedValueOnce(sseResponse("", { status: 503 }));

    await expect(
      streamAgentChat({ child_id: "c1", message: "hi" }, {}),
    ).rejects.toThrow(/503/);
  });
});
