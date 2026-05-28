import { describe, it, expect } from "vitest";

import { relativeTime, sessionDisplayTitle } from "./sessionListHelpers";
import type { AgentChatSessionSummary } from "@/types/api";

function s(overrides: Partial<AgentChatSessionSummary> = {}): AgentChatSessionSummary {
  return {
    session_id: "s1",
    child_id: "c1",
    title: "",
    last_message_preview: "",
    archived_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("sessionDisplayTitle", () => {
  it("returns the title when present", () => {
    expect(sessionDisplayTitle(s({ title: "Dinosaur story" }))).toBe("Dinosaur story");
  });
  it("falls back to 'New chat' when blank", () => {
    expect(sessionDisplayTitle(s({ title: "   " }))).toBe("New chat");
    expect(sessionDisplayTitle(s({ title: "" }))).toBe("New chat");
  });
});

describe("relativeTime", () => {
  const now = Date.parse("2026-05-28T12:00:00Z");

  it("returns 'just now' for very recent", () => {
    expect(relativeTime("2026-05-28T11:59:40Z", now)).toBe("just now");
  });
  it("returns minutes", () => {
    expect(relativeTime("2026-05-28T11:50:00Z", now)).toBe("10m");
  });
  it("returns hours", () => {
    expect(relativeTime("2026-05-28T09:00:00Z", now)).toBe("3h");
  });
  it("returns days", () => {
    expect(relativeTime("2026-05-26T12:00:00Z", now)).toBe("2d");
  });
  it("returns a short date when older than a week", () => {
    expect(relativeTime("2026-05-01T12:00:00Z", now)).toBe("5/1");
  });
  it("returns empty string for an unparseable input", () => {
    expect(relativeTime("not-a-date", now)).toBe("");
  });
});
