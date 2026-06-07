import { describe, expect, it } from "vitest";
import {
  captionsDefaultForAge,
  isEndButtonEnabled,
  isPanelVisible,
  nextPendingGate,
  pickIndicator,
  resolveCaptionsVisibility,
  shouldShowEntryButton,
  shouldShowHeaderTalkPill,
  TALK_PANEL_STATE_COPY,
} from "@/pages/MyAgentPage/talkToBuddyHelpers";
import type { VoiceConversationState } from "@/hooks/voiceConversationStateMachine";

const ALL_STATES: VoiceConversationState[] = [
  "idle",
  "connecting",
  "listening",
  "thinking",
  "speaking",
  "interrupted",
  "ending",
  "error",
  "unsupported",
];

describe("TALK_PANEL_STATE_COPY (#618)", () => {
  it("covers every state in the reducer", () => {
    for (const state of ALL_STATES) {
      expect(TALK_PANEL_STATE_COPY[state]).toBeDefined();
      expect(TALK_PANEL_STATE_COPY[state].length).toBeGreaterThan(10);
    }
  });

  it("unsupported copy points the user to typed chat", () => {
    expect(TALK_PANEL_STATE_COPY.unsupported.toLowerCase()).toContain("typ");
  });

  it("error copy offers a recovery path", () => {
    const copy = TALK_PANEL_STATE_COPY.error.toLowerCase();
    expect(copy).toMatch(/try again|typing|switch/);
  });
});

describe("shouldShowEntryButton (#618)", () => {
  const baseline = {
    supportsVoice: true,
    micConsentGranted: true,
    voiceConversationConsentGranted: true,
    hasCurrentChild: true,
  };

  it("shows the button only when every precondition is met", () => {
    expect(shouldShowEntryButton(baseline)).toBe(true);
  });

  it("hides when voice support is missing", () => {
    expect(
      shouldShowEntryButton({ ...baseline, supportsVoice: false }),
    ).toBe(false);
  });

  it("hides when microphone consent is missing", () => {
    expect(
      shouldShowEntryButton({ ...baseline, micConsentGranted: false }),
    ).toBe(false);
  });

  it("hides when voice_conversation_consent is missing", () => {
    expect(
      shouldShowEntryButton({
        ...baseline,
        voiceConversationConsentGranted: false,
      }),
    ).toBe(false);
  });

  it("hides when no child profile is selected", () => {
    expect(
      shouldShowEntryButton({ ...baseline, hasCurrentChild: false }),
    ).toBe(false);
  });
});

describe("isPanelVisible (#618)", () => {
  it("hides only on the terminal unsupported state", () => {
    for (const state of ALL_STATES) {
      const visible = isPanelVisible(state);
      expect(visible).toBe(state !== "unsupported");
    }
  });
});

describe("isEndButtonEnabled (#618)", () => {
  it("enables the End button during any active session state", () => {
    const active: VoiceConversationState[] = [
      "connecting",
      "listening",
      "thinking",
      "speaking",
      "interrupted",
      "ending",
    ];
    for (const state of active) {
      expect(isEndButtonEnabled(state)).toBe(true);
    }
  });

  it("disables the End button when there is no active session", () => {
    const inactive: VoiceConversationState[] = ["idle", "error", "unsupported"];
    for (const state of inactive) {
      expect(isEndButtonEnabled(state)).toBe(false);
    }
  });
});

describe("pickIndicator (#618)", () => {
  it("reduced-motion users always get the static pill", () => {
    for (const state of ALL_STATES) {
      expect(pickIndicator(state, true)).toBe("static");
    }
  });

  it("listening + interrupted → pulse-listening (kid speaking)", () => {
    expect(pickIndicator("listening", false)).toBe("pulse-listening");
    expect(pickIndicator("interrupted", false)).toBe("pulse-listening");
  });

  it("thinking + speaking → pulse-speaking (buddy active)", () => {
    expect(pickIndicator("thinking", false)).toBe("pulse-speaking");
    expect(pickIndicator("speaking", false)).toBe("pulse-speaking");
  });

  it("everything else gets a static indicator even without reduced motion", () => {
    const staticStates: VoiceConversationState[] = [
      "idle",
      "connecting",
      "ending",
      "error",
      "unsupported",
    ];
    for (const state of staticStates) {
      expect(pickIndicator(state, false)).toBe("static");
    }
  });
});

describe("nextPendingGate (#620)", () => {
  it("returns 'mic' when both consents are missing", () => {
    expect(
      nextPendingGate({ micConsent: false, voiceConsent: false }),
    ).toBe("mic");
  });

  it("returns 'voice' when mic is granted but voice is missing", () => {
    expect(
      nextPendingGate({ micConsent: true, voiceConsent: false }),
    ).toBe("voice");
  });

  it("returns null when both consents are granted", () => {
    expect(
      nextPendingGate({ micConsent: true, voiceConsent: true }),
    ).toBe(null);
  });

  it("defensively returns 'mic' for a null child (defer to grown-up)", () => {
    expect(nextPendingGate(null)).toBe("mic");
    expect(nextPendingGate(undefined)).toBe("mic");
  });

  it("treats undefined consent fields as not-granted (mic missing case)", () => {
    expect(nextPendingGate({})).toBe("mic");
  });

  it("treats undefined voice consent as not-granted when mic is true", () => {
    expect(nextPendingGate({ micConsent: true })).toBe("voice");
  });
});

describe("shouldShowHeaderTalkPill (#636)", () => {
  const allGranted = {
    supportsVoice: true,
    micConsentGranted: true,
    voiceConversationConsentGranted: true,
    hasCurrentChild: true,
  };

  it("shows the pill when consents + capability are ready and no stream/bubble is active", () => {
    expect(shouldShowHeaderTalkPill(allGranted, false, false)).toBe(true);
  });

  it("hides while the chat is streaming a text response", () => {
    // Pressing Start mid-stream would race the AbortController flow.
    expect(shouldShowHeaderTalkPill(allGranted, true, false)).toBe(false);
  });

  it("hides while the inline voice bubble is already open", () => {
    // The bubble has replaced the composer; a second entry point in
    // the header would be redundant + confusing.
    expect(shouldShowHeaderTalkPill(allGranted, false, true)).toBe(false);
  });

  it("hides when both streaming and talk-open are true (sanity)", () => {
    expect(shouldShowHeaderTalkPill(allGranted, true, true)).toBe(false);
  });

  it("delegates capability/consent gating to shouldShowEntryButton", () => {
    // Any single precondition failure must hide the pill, no matter
    // what the streaming/talk-open state is.
    const cases = [
      { ...allGranted, supportsVoice: false },
      { ...allGranted, micConsentGranted: false },
      { ...allGranted, voiceConversationConsentGranted: false },
      { ...allGranted, hasCurrentChild: false },
    ];
    for (const broken of cases) {
      expect(shouldShowHeaderTalkPill(broken, false, false)).toBe(false);
    }
  });
});

describe("captionsDefaultForAge (#608)", () => {
  // Per PRD §3.16: pre-readers (3-5) get captions OFF by default; the
  // running text is distracting next to the BuddyOrb and they can't
  // read it anyway. Older bands get captions ON so they can follow
  // along + reread tricky words.
  it("returns false for pre-reader ages (under 6)", () => {
    expect(captionsDefaultForAge(3)).toBe(false);
    expect(captionsDefaultForAge(4)).toBe(false);
    expect(captionsDefaultForAge(5)).toBe(false);
  });

  it("returns true for the 6-8 band", () => {
    expect(captionsDefaultForAge(6)).toBe(true);
    expect(captionsDefaultForAge(7)).toBe(true);
    expect(captionsDefaultForAge(8)).toBe(true);
  });

  it("returns true for the 9-12 band", () => {
    expect(captionsDefaultForAge(9)).toBe(true);
    expect(captionsDefaultForAge(12)).toBe(true);
  });

  it("returns true when the age is unknown (null / undefined)", () => {
    // Defensive default — if the profile hasn't loaded yet, prefer
    // showing captions. Worst case is a 3-year-old gets a few lines
    // of text for a beat; the alternative (silently hiding captions
    // for an older kid) would feel broken.
    expect(captionsDefaultForAge(null)).toBe(true);
    expect(captionsDefaultForAge(undefined)).toBe(true);
  });

  it("treats the 6-vs-5 boundary inclusively (6 is on, 5 is off)", () => {
    // Lock the boundary so a future contributor can't drift it.
    expect(captionsDefaultForAge(5)).toBe(false);
    expect(captionsDefaultForAge(6)).toBe(true);
  });
});

describe("resolveCaptionsVisibility (#608)", () => {
  it("uses the per-age default when no override is passed", () => {
    expect(resolveCaptionsVisibility(4, undefined)).toBe(false);
    expect(resolveCaptionsVisibility(7, undefined)).toBe(true);
    expect(resolveCaptionsVisibility(11, undefined)).toBe(true);
  });

  it("forces captions on when override is true (safety_block path)", () => {
    // The whole point of the override: after a safety_block event,
    // captions must auto-show regardless of age. This is the load-
    // bearing path the panel uses to surface the fallback sentence.
    expect(resolveCaptionsVisibility(4, true)).toBe(true);
    expect(resolveCaptionsVisibility(3, true)).toBe(true);
    expect(resolveCaptionsVisibility(null, true)).toBe(true);
  });

  it("ignores override=false to avoid accidentally silencing readers", () => {
    // ``false`` would hide captions for an older kid who should see
    // them. The override semantic is "force on" — explicit-false from
    // a half-wired parent falls back to the per-age default.
    expect(resolveCaptionsVisibility(8, false)).toBe(true);
    expect(resolveCaptionsVisibility(4, false)).toBe(false);
  });
});
