/**
 * OnboardingModal — first-login auto-opening flow that walks the user
 * through naming, avatar, title, and a parent-consent gate, then calls
 * POST /me/onboarding/complete (#440) to flip users.onboarded_at on
 * the server and sync the auth store.
 *
 * Per PRD §3.11.2 the step list shrinks for younger children:
 *   3-5: avatar-only path with auto-suggested buddy name
 *   6-8: name + avatar + curated title
 *   9-12: full flow with optional free-text title
 *
 * Pure step-decision logic lives in onboardingState.ts so it's unit-testable
 * without mounting the modal.
 *
 * Issue: #443 | Parent epic: #436
 */

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { AxiosError } from "axios";
import { Shuffle } from "lucide-react";
import { ANIMAL_EMOJIS } from "@/lib/avatars";
import { AnimalAvatarIcon } from "@/lib/avatarIcons";
import { CURATED_TITLES, customTitleAllowed } from "@/lib/agentTitles";
import { useUpsertAgent } from "@/hooks/useAgent";
import { onboardingService } from "@/api/services/onboardingService";
import useAuthStore from "@/store/useAuthStore";
import type { AgeGroup } from "@/types/api";
import type { AgentErrorDetail } from "@/types/agent";
import {
  AUTO_NAME_SUGGESTIONS,
  stepsForAge,
  type OnboardingStepKey,
} from "./onboardingState";

const MAX_NAME = 32;
const MAX_TITLE = 32;

interface Props {
  open: boolean;
  childId: string;
  ageGroup: AgeGroup | undefined | null;
  onClose: () => void;
}

function avatarIdFor(emoji: string): string {
  return `emoji:${emoji}`;
}

function detailFrom(err: unknown): AgentErrorDetail | null {
  if (!(err instanceof AxiosError)) return null;
  const data = err.response?.data;
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail: unknown }).detail;
    if (d && typeof d === "object" && "code" in d) {
      return d as AgentErrorDetail;
    }
  }
  return null;
}

function pickRandomName(): string {
  const i = Math.floor(Math.random() * AUTO_NAME_SUGGESTIONS.length);
  return AUTO_NAME_SUGGESTIONS[i];
}

export default function OnboardingModal({
  open,
  childId,
  ageGroup,
  onClose,
}: Props) {
  const upsert = useUpsertAgent();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const canGrantParentConsent = user?.role === "parent";

  const steps = useMemo(() => stepsForAge(ageGroup), [ageGroup]);
  const [stepIdx, setStepIdx] = useState(0);
  const [name, setName] = useState(() =>
    ageGroup === "3-5" ? pickRandomName() : "",
  );
  const [avatarId, setAvatarId] = useState<string>(
    avatarIdFor(ANIMAL_EMOJIS[0]),
  );
  const [title, setTitle] = useState<string>(CURATED_TITLES[0]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Reset state whenever the modal is opened so a re-open shows step 1.
  useEffect(() => {
    if (open) {
      setStepIdx(0);
      setError(null);
      if (ageGroup === "3-5" && !name.trim()) {
        setName(pickRandomName());
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;
  const currentStep: OnboardingStepKey | undefined = steps[stepIdx];
  const isLast = stepIdx >= steps.length - 1;

  const goNext = () => {
    setError(null);
    if (stepIdx < steps.length - 1) {
      setStepIdx(stepIdx + 1);
    }
  };

  const goBack = () => {
    setError(null);
    if (stepIdx > 0) setStepIdx(stepIdx - 1);
  };

  const handleConsent = async () => {
    setError(null);
    if (!canGrantParentConsent) {
      setError("Ask a parent or guardian to approve this buddy before sharing.");
      return;
    }
    setBusy(true);
    try {
      // 1. Upsert the buddy (safety-checked server-side).
      await upsert.mutateAsync({
        agent_name: name.trim(),
        agent_avatar_id: avatarId,
        agent_title: title.trim(),
        child_id: childId,
      });
      // 2. Mark onboarding complete with parent consent.
      const updated = await onboardingService.completeOnboarding({
        parent_consent: true,
        child_id: childId,
      });
      // 3. Sync the auth store so RequireOnboarded stops redirecting.
      setUser(updated);
      onClose();
    } catch (err) {
      const detail = detailFrom(err);
      if (detail?.code === "INVALID_AVATAR") {
        setError("Pick a different animal — that one isn't allowed.");
        setStepIdx(steps.indexOf("avatar"));
      } else if (
        detail?.code === "UNSAFE_AGENT_NAME" ||
        detail?.code === "INVALID_AGENT_NAME"
      ) {
        setError(detail.reason ?? "Try a different name.");
        const ni = steps.indexOf("name");
        if (ni >= 0) setStepIdx(ni);
      } else if (
        detail?.code === "UNSAFE_AGENT_TITLE" ||
        detail?.code === "INVALID_AGENT_TITLE"
      ) {
        setError(detail.reason ?? "Try a different title.");
        const ti = steps.indexOf("title");
        if (ti >= 0) setStepIdx(ti);
      } else if (detail?.code === "SAFETY_UNAVAILABLE") {
        setError("Our safety checker is taking a break. Try again in a minute.");
      } else {
        setError("We couldn't save your buddy. Try again in a moment.");
      }
    } finally {
      setBusy(false);
    }
  };

  const modal = (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
      className="fixed inset-0 z-[120] flex items-center justify-center bg-black/40 px-4 py-8"
    >
      <div className="relative z-[121] w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <header className="flex flex-col gap-1">
          <p className="text-xs uppercase tracking-wide text-primary-dark">
            Step {stepIdx + 1} of {steps.length}
          </p>
          <h2 id="onboarding-title" className="text-xl font-semibold text-gray-900">
            {currentStep === "greeting" && "Hi! I'm your creative buddy."}
            {currentStep === "name" && "What should I call you?"}
            {currentStep === "avatar" && "Which animal am I?"}
            {currentStep === "title" && "What's my title?"}
            {currentStep === "consent" && "Meet your child's creative buddy"}
          </h2>
        </header>

        <div className="mt-4 flex flex-col gap-4">
          {currentStep === "greeting" && (
            <div className="flex flex-col gap-2 text-sm text-gray-700">
              <p>
                I'm going to help you make stories. Let's pick what I look like
                and what you call me — you can always change it later.
              </p>
            </div>
          )}

          {currentStep === "name" && (
            <div className="flex flex-col gap-2">
              <label htmlFor="ob-name" className="text-sm font-medium text-gray-700">
                Buddy name
              </label>
              <input
                id="ob-name"
                type="text"
                className="k12-input w-full"
                value={name}
                maxLength={MAX_NAME}
                onChange={(e) => setName(e.target.value.slice(0, MAX_NAME))}
                placeholder="e.g. Sparkle"
              />
              <p className="text-xs text-gray-500">
                {name.length}/{MAX_NAME}
              </p>
            </div>
          )}

          {currentStep === "avatar" && (
            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium text-gray-700">
                Pick a buddy icon
              </span>
              <div role="radiogroup" className="grid grid-cols-5 gap-2">
                {ANIMAL_EMOJIS.map((emoji, index) => {
                  const id = avatarIdFor(emoji);
                  const selected = avatarId === id;
                  return (
                    <button
                      key={emoji}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      aria-label={`Choose buddy icon ${index + 1}`}
                      onClick={() => setAvatarId(id)}
                      className={[
                        "flex aspect-square items-center justify-center rounded-lg border-2 text-primary transition-colors",
                        selected
                          ? "border-primary bg-primary/10"
                          : "border-gray-200 hover:border-primary/35 hover:bg-primary/5",
                      ].join(" ")}
                    >
                      <AnimalAvatarIcon avatarId={id} size={22} />
                    </button>
                  );
                })}
              </div>
              {ageGroup === "3-5" && (
                <p className="text-xs text-gray-500">
                  We'll call your buddy <strong>{name}</strong>. Tap{" "}
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 text-primary-dark underline"
                    onClick={() => setName(pickRandomName())}
                  >
                    <Shuffle className="h-3 w-3" aria-hidden="true" /> shuffle
                  </button>{" "}
                  for a different name.
                </p>
              )}
            </div>
          )}

          {currentStep === "title" && (
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-700">
                Pick a title
              </label>
              <select
                className="k12-input w-full"
                value={CURATED_TITLES.includes(title as never) ? title : "__custom__"}
                onChange={(e) => {
                  if (e.target.value === "__custom__") setTitle("");
                  else setTitle(e.target.value);
                }}
              >
                {CURATED_TITLES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
                {customTitleAllowed(ageGroup) && (
                  <option value="__custom__">Custom title</option>
                )}
              </select>
              {customTitleAllowed(ageGroup) &&
                !CURATED_TITLES.includes(title as never) && (
                  <input
                    type="text"
                    className="k12-input w-full"
                    value={title}
                    maxLength={MAX_TITLE}
                    onChange={(e) =>
                      setTitle(e.target.value.slice(0, MAX_TITLE))
                    }
                    placeholder="Type a custom title (1-32 chars)"
                  />
                )}
            </div>
          )}

          {currentStep === "consent" && (
            <div className="flex flex-col gap-3 text-sm text-gray-700">
              {canGrantParentConsent ? (
                <>
                  <p className="font-medium">For the parent / guardian</p>
                  <p>
                    This buddy is the name and animal your child picks to show on
                    stories they share publicly in Content Hub. We never show your
                    child's real name, email, or username — only the buddy.
                  </p>
                  <p>
                    You can change the buddy any time from "My Agent". Past stories
                    keep the buddy that posted them, so your child's creative
                    timeline stays consistent.
                  </p>
                  <p className="text-xs text-gray-500">
                    Note: We re-check the buddy's name and title for safety every
                    time it's edited.
                  </p>
                </>
              ) : (
                <>
                  <p className="font-medium">Parent approval needed</p>
                  <p>
                    A parent or guardian needs to approve this buddy before it can
                    be used for public sharing. You can still save your choices and
                    come back with a parent later.
                  </p>
                </>
              )}
            </div>
          )}

          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}
        </div>

        <footer className="mt-6 flex items-center justify-between">
          {stepIdx > 0 ? (
            <button
              type="button"
              className="text-sm font-medium text-gray-600 hover:text-gray-900"
              onClick={goBack}
              disabled={busy}
            >
              ← Back
            </button>
          ) : (
            <span />
          )}

          {currentStep === "consent" ? (
            <div className="flex gap-2">
              <button
                type="button"
                className="k12-button-secondary"
                onClick={onClose}
                disabled={busy}
              >
                Not now
              </button>
              <button
                type="button"
                className="k12-button-primary"
                onClick={handleConsent}
                disabled={busy || !canGrantParentConsent || !name.trim() || !title.trim()}
              >
                {busy ? "Saving…" : "I'm a parent and I'm OK with this"}
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="k12-button-primary"
              onClick={goNext}
              disabled={
                (currentStep === "name" && !name.trim()) ||
                (currentStep === "title" && !title.trim()) ||
                isLast
              }
            >
              Next →
            </button>
          )}
        </footer>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
