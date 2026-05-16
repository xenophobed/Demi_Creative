/**
 * PersonaEditorSheet — modal/sheet that lets the user tweak an existing
 * buddy persona (name, avatar, title). Replaces the always-visible
 * editor under the chat panel (#510 follow-up): now triggered by a
 * Configure button in the chat header, so the chat is the primary
 * surface and the editor only appears when the user reaches for it.
 *
 * Owns its own form state — pre-populates from the existing agent on
 * open, calls PUT /me/agent via useUpsertAgent on save, maps
 * server-side detail.code values back to per-field inline errors.
 *
 * Parent epic: #436
 */

import { useEffect, useState } from "react";
import { AxiosError } from "axios";
import { X } from "lucide-react";
import { ANIMAL_EMOJIS } from "@/lib/avatars";
import { useUpsertAgent } from "@/hooks/useAgent";
import type { Agent, AgentErrorDetail } from "@/types/agent";
import type { AgeGroup } from "@/types/api";
import AgentTitlePicker from "./AgentTitlePicker";

const MAX_NAME = 32;

interface FieldErrors {
  name?: string;
  avatar?: string;
  title?: string;
  general?: string;
}

interface Props {
  open: boolean;
  agent: Agent;
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

export default function PersonaEditorSheet({
  open,
  agent,
  childId,
  ageGroup,
  onClose,
}: Props) {
  const upsert = useUpsertAgent();
  const [name, setName] = useState(agent.agent_name);
  const [avatarId, setAvatarId] = useState(agent.agent_avatar_id);
  const [title, setTitle] = useState(agent.agent_title);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Re-hydrate when the agent changes OR the sheet opens, so a stale
  // edit from a prior open doesn't carry into the new session.
  useEffect(() => {
    if (open) {
      setName(agent.agent_name);
      setAvatarId(agent.agent_avatar_id);
      setTitle(agent.agent_title);
      setErrors({});
      setSavedAt(null);
    }
  }, [open, agent.agent_name, agent.agent_avatar_id, agent.agent_title]);

  if (!open) return null;

  const onSave = async () => {
    setErrors({});
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
      // Close on success after a short beat so the success toast is
      // visible. Trade-off: feels snappier than the user manually
      // dismissing, and the chat-side header reflects the change anyway.
      setTimeout(() => onClose(), 600);
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
          setErrors({
            general: detail.reason ?? "Something went wrong saving your buddy.",
          });
      }
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="persona-editor-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-8"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h2
              id="persona-editor-title"
              className="text-xl font-semibold text-gray-900"
            >
              Configure your buddy
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Tweak the name, animal, or title. Saved changes show up in
              chat and on any new posts.
            </p>
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            disabled={upsert.isPending}
            className="rounded-full p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </header>

        <div className="mt-5 flex flex-col gap-5">
          {/* Name */}
          <div className="flex flex-col gap-2">
            <label
              htmlFor="persona-name"
              className="text-sm font-medium text-gray-700"
            >
              Buddy name
            </label>
            <input
              id="persona-name"
              type="text"
              className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 disabled:bg-gray-100"
              value={name}
              maxLength={MAX_NAME}
              placeholder="e.g. Sparkle"
              disabled={upsert.isPending}
              onChange={(e) => setName(e.target.value.slice(0, MAX_NAME))}
              aria-describedby="persona-name-counter"
            />
            <div className="flex items-center justify-between">
              <p id="persona-name-counter" className="text-xs text-gray-500">
                {name.length}/{MAX_NAME}
              </p>
              {errors.name && (
                <p className="text-xs text-red-600">{errors.name}</p>
              )}
            </div>
          </div>

          {/* Avatar */}
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-gray-700">
              Buddy animal
            </span>
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

          {/* Status + Save */}
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
          </div>
        </div>

        <footer className="mt-6 flex items-center justify-end gap-2">
          <button
            type="button"
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50"
            onClick={onClose}
            disabled={upsert.isPending}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-violet-700 focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:bg-gray-300"
            disabled={upsert.isPending}
            onClick={onSave}
          >
            {upsert.isPending ? "Saving…" : "Save buddy"}
          </button>
        </footer>
      </div>
    </div>
  );
}
