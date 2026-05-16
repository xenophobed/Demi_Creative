/**
 * launch_flow contract tests (#496).
 *
 * Two layers are exercised here:
 *
 *   1. `buildLaunchFlowPath` — the pure helper that converts a
 *      `launch_flow` SSE payload into a navigable path with prefill
 *      query params. Pure function so we can pin it without spinning
 *      up React Router.
 *
 *   2. `consumeSSEStream` — the shared SSE dispatcher must recognise
 *      the new `launch_flow` event type and route it to
 *      `callbacks.onLaunchFlow`. If an SPA omits that callback, the
 *      stream must NOT throw (older clients should ignore the event
 *      and fall back to the regular text reply per the issue body).
 */
import { describe, expect, it, vi } from "vitest";
import { buildLaunchFlowPath } from "@/hooks/useLaunchFlowNavigation";
import { consumeSSEStream } from "@/api/utils/sseStream";
import type { SSELaunchFlowData, StreamCallbacks } from "@/types/api";

function streamResponse(body: string): Response {
  // Encode the SSE blob into a single-shot ReadableStream — matches
  // what fetch() yields for a server-sent-events response.
  return {
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(body));
        controller.close();
      },
    }),
  } as Response;
}

describe("buildLaunchFlowPath", () => {
  it("preserves the route when prefill is empty", () => {
    const data: SSELaunchFlowData = {
      flow_type: "image_story",
      route: "/story/stry_abc",
      prefill: {},
    };
    expect(buildLaunchFlowPath(data)).toBe("/story/stry_abc");
  });

  it("appends prefill as query params", () => {
    const data: SSELaunchFlowData = {
      flow_type: "interactive_story",
      route: "/interactive",
      prefill: { session: "sess_xyz", age_group: "6-8", theme: "forest" },
    };
    const path = buildLaunchFlowPath(data);
    expect(path.startsWith("/interactive?")).toBe(true);
    const params = new URLSearchParams(path.split("?")[1]);
    expect(params.get("session")).toBe("sess_xyz");
    expect(params.get("age_group")).toBe("6-8");
    expect(params.get("theme")).toBe("forest");
  });

  it("skips null/undefined prefill values", () => {
    const data: SSELaunchFlowData = {
      flow_type: "kids_daily",
      route: "/kids-daily/ep_1",
      prefill: { episode_id: "ep_1", theme: null },
    };
    const path = buildLaunchFlowPath(data);
    expect(path).toContain("episode_id=ep_1");
    expect(path).not.toContain("theme=");
  });

  it("URL-encodes special characters in prefill values", () => {
    const data: SSELaunchFlowData = {
      flow_type: "image_story",
      route: "/upload",
      prefill: { theme: "outer space & stars" },
    };
    const path = buildLaunchFlowPath(data);
    // URLSearchParams encodes spaces as '+' and ampersands as '%26'.
    expect(path).toContain("theme=outer+space+%26+stars");
  });
});

describe("consumeSSEStream — launch_flow event", () => {
  it("routes the launch_flow event to onLaunchFlow with the parsed payload", async () => {
    const payload: SSELaunchFlowData = {
      flow_type: "image_story",
      route: "/story/stry_123",
      prefill: { story_id: "stry_123", child_id: "c1" },
    };
    const blob = `event: launch_flow\ndata: ${JSON.stringify(payload)}\n\n`;
    const onLaunchFlow = vi.fn();
    const callbacks: StreamCallbacks = { onLaunchFlow };
    await consumeSSEStream(streamResponse(blob), callbacks);
    expect(onLaunchFlow).toHaveBeenCalledTimes(1);
    expect(onLaunchFlow).toHaveBeenCalledWith(payload);
  });

  it("silently ignores launch_flow when no onLaunchFlow callback is registered", async () => {
    // Older clients (pre-#496) won't have onLaunchFlow wired up. The
    // SSE dispatcher must not throw — the user should still receive
    // the regular text reply via onResult. Acceptance criteria: "If
    // the frontend SSE handler is older and doesn't understand
    // launch_flow, the user still sees a fallback text reply".
    const launchBlob = `event: launch_flow\ndata: {"flow_type":"kids_daily","route":"/kids-daily/ep_1","prefill":{}}\n\n`;
    const resultBlob = `event: result\ndata: {"message":"Episode ready!"}\n\n`;
    const onResult = vi.fn();
    await consumeSSEStream(
      streamResponse(launchBlob + resultBlob),
      { onResult } as StreamCallbacks,
    );
    expect(onResult).toHaveBeenCalledTimes(1);
  });
});
