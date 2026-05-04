/**
 * MyAgentPage — view + edit of the user's buddy persona (#442).
 *
 * Renders:
 *   - Welcome header (uses the active child's name when available)
 *   - Agent name input (max 32) with character counter and inline error
 *   - 5x4 avatar grid sourced from the shared ANIMAL_EMOJIS list
 *   - AgentTitlePicker (curated dropdown + free-text for ages 9-12)
 *   - Save button (disabled while pending), with success + failure toasts
 *
 * Backend contract (#439):
 *   - PUT /me/agent rejects with detail.code = INVALID_AVATAR / UNSAFE_*
 *     so we can map the failure back to the right field.
 *
 * NOTE: This page does NOT add the navigation entry or the
 * <RequireOnboarded> route gate — those land in #444.
 */

import { useEffect, useMemo, useState } from "react";
import { AxiosError } from "axios";
import { ANIMAL_EMOJIS } from "@/lib/avatars";
import useChildStore from "@/store/useChildStore";
import useAuthStore from "@/store/useAuthStore";
import { useAgent, useUpsertAgent } from "@/hooks/useAgent";
import AgentTitlePicker from "./AgentTitlePicker";
import OnboardingModal from "./OnboardingModal";
import { shouldAutoOpenOnboarding } from "./onboardingState";
import type { AgentErrorDetail } from "@/types/agent";

const MAX_NAME = 32;

interface FieldErrors {
  name?: string;
  avatar?: string;
  title?: string;
  general?: string;
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

export default function MyAgentPage() {
  const currentChild = useChildStore((s) => s.currentChild);
  const defaultChildId = useChildStore((s) => s.defaultChildId);
  const childId = currentChild?.child_id ?? defaultChildId;
  const ageGroup = currentChild?.age_group;

  const { data: existing, isLoading } = useAgent(childId);
  const upsert = useUpsertAgent();

  // First-login modal: auto-opens when authenticated user has not yet
  // completed onboarding (#443). The modal walks through name/avatar/title
  // + parent consent and calls POST /me/onboarding/complete on submit.
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const onboardedAt = useAuthStore((s) => s.user?.onboarded_at);
  const [modalOpen, setModalOpen] = useState(false);
  useEffect(() => {
    if (isLoading) return;
    if (
      shouldAutoOpenOnboarding({
        isAuthenticated,
        onboardedAt,
        hasExistingAgent: existing != null,
      })
    ) {
      setModalOpen(true);
    }
  }, [isAuthenticated, onboardedAt, existing, isLoading]);

  const [name, setName] = useState("");
  const [avatarId, setAvatarId] = useState<string>(
    avatarIdFor(ANIMAL_EMOJIS[0]),
  );
  const [title, setTitle] = useState("Story Wizard");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Hydrate form when the existing agent loads.
  useEffect(() => {
    if (existing) {
      setName(existing.agent_name);
      setAvatarId(existing.agent_avatar_id);
      setTitle(existing.agent_title);
    }
  }, [existing]);

  const childGreeting = useMemo(() => {
    const childName = currentChild?.name?.trim();
    return childName ? `${childName}'s creative buddy` : "Meet your creative buddy";
  }, [currentChild?.name]);

  const onSave = async () => {
    setErrors({});
    if (!childId) {
      setErrors({ general: "No active child profile found." });
      return;
    }
    if (!name.trim()) {
      setErrors({ name: "Give your buddy a name (1-32 characters)." });
      return;
    }
    if (!title.trim()) {
      setErrors({ title: "Pick a title or write your own." });
      return;
    }
    try {
      await upsert.mutateAsync({
        agent_name: name.trim(),
        agent_avatar_id: avatarId,
        agent_title: title.trim(),
        child_id: childId,
      });
      setSavedAt(Date.now());
    } catch (err) {
      const detail = detailFrom(err);
      if (!detail) {
        setErrors({
          general: "We couldn't save your buddy. Try again in a moment.",
        });
        return;
      }
      switch (detail.code) {
        case "INVALID_AVATAR":
          setErrors({ avatar: "Pick a different animal — that one isn't allowed." });
          break;
        case "UNSAFE_AGENT_NAME":
        case "INVALID_AGENT_NAME":
          setErrors({
            name:
              detail.reason ??
              "Try a different name — that one didn't pass our safety check.",
          });
          break;
        case "UNSAFE_AGENT_TITLE":
        case "INVALID_AGENT_TITLE":
          setErrors({
            title:
              detail.reason ??
              "Try a different title — that one didn't pass our safety check.",
          });
          break;
        case "SAFETY_UNAVAILABLE":
          setErrors({
            general:
              "Our safety checker is taking a break. Please try again in a minute.",
          });
          break;
        default:
          setErrors({ general: detail.reason ?? "Something went wrong saving your buddy." });
      }
    }
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
      <OnboardingModal
        open={modalOpen}
        childId={childId}
        ageGroup={ageGroup}
        onClose={() => setModalOpen(false)}
      />
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-gray-900">{childGreeting}</h1>
        <p className="text-sm text-gray-600">
          Your buddy is the name and animal we'll show whenever you share a story.
          Pick anything you like — you can always change it later.
        </p>
      </header>

      {isLoading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <section className="flex flex-col gap-6 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          {/* Name */}
          <div className="flex flex-col gap-2">
            <label htmlFor="agent-name" className="text-sm font-medium text-gray-700">
              Buddy name
            </label>
            <input
              id="agent-name"
              type="text"
              className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 disabled:bg-gray-100"
              value={name}
              maxLength={MAX_NAME}
              placeholder="e.g. Sparkle"
              disabled={upsert.isPending}
              onChange={(e) => setName(e.target.value.slice(0, MAX_NAME))}
              aria-describedby="agent-name-counter"
            />
            <div className="flex items-center justify-between">
              <p id="agent-name-counter" className="text-xs text-gray-500">
                {name.length}/{MAX_NAME}
              </p>
              {errors.name && (
                <p className="text-xs text-red-600">{errors.name}</p>
              )}
            </div>
          </div>

          {/* Avatar */}
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-gray-700">Buddy animal</span>
            <div
              role="radiogroup"
              aria-label="Buddy animal"
              className="grid grid-cols-5 gap-2"
            >
              {ANIMAL_EMOJIS.map((emoji) => {
                const id = avatarIdFor(emoji);
                const selected = avatarId === id;
                return (
                  <button
                    key={emoji}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    aria-label={`Choose ${emoji}`}
                    disabled={upsert.isPending}
                    onClick={() => setAvatarId(id)}
                    className={[
                      "flex aspect-square items-center justify-center rounded-xl border-2 text-2xl transition-colors focus:outline-none focus:ring-2 focus:ring-violet-500",
                      selected
                        ? "border-violet-500 bg-violet-50"
                        : "border-gray-200 hover:border-gray-300",
                    ].join(" ")}
                  >
                    {emoji}
                  </button>
                );
              })}
            </div>
            {errors.avatar && (
              <p className="text-xs text-red-600">{errors.avatar}</p>
            )}
          </div>

          {/* Title */}
          <AgentTitlePicker
            value={title}
            onChange={setTitle}
            ageGroup={ageGroup}
            disabled={upsert.isPending}
            error={errors.title ?? null}
          />

          {/* Save */}
          <div className="flex flex-col gap-2">
            {errors.general && (
              <p className="text-sm text-red-600" role="alert">
                {errors.general}
              </p>
            )}
            {savedAt && !errors.general && (
              <p className="text-sm text-emerald-600" role="status">
                Buddy saved!
              </p>
            )}
            <button
              type="button"
              className="self-end rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:bg-gray-300"
              disabled={upsert.isPending}
              onClick={onSave}
            >
              {upsert.isPending ? "Saving…" : existing ? "Save buddy" : "Meet my buddy"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
