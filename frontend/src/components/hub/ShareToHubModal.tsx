/**
 * ShareToHubModal — group picker + caption input for sharing a story
 * to Content Hub (#453).
 *
 * Reuses the hubService client landed in #451:
 *   - listGroups() for the group picker
 *   - createHubPost(groupId, payload) for the actual share
 *
 * Server-side gates (#449) that we surface as friendly errors:
 *   - 412 ONBOARDING_REQUIRED -> "Finish meeting your buddy first"
 *     (the modal closes and routes the user to /my-agent)
 *   - 412 AGENT_REQUIRED      -> same as above
 *   - 403 NOT_A_MEMBER        -> "You'll need to join this group first"
 *   - 400 UNSAFE_CAPTION      -> inline error on the caption field
 *   - 503 SAFETY_UNAVAILABLE  -> "Try again in a minute" toast
 *
 * Issue: #453 | Parent epic: #437
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AxiosError } from "axios";
import { useQuery } from "@tanstack/react-query";
import { hubService } from "@/api/services/hubService";
import type { Group } from "@/types/hub";

const MAX_CAPTION = 280;

interface Props {
  open: boolean;
  onClose: () => void;
  source: {
    artifact_type: "art_story" | "interactive_story" | "kids_daily";
    source_id: string;
  };
  /** Optional success callback — receives the new post_id. */
  onShared?: (postId: string, groupSlug: string) => void;
}

export default function ShareToHubModal({
  open,
  onClose,
  source,
  onShared,
}: Props) {
  const navigate = useNavigate();
  const [groupId, setGroupId] = useState<string>("");
  const [caption, setCaption] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["hub-groups"],
    queryFn: () => hubService.listGroups(),
    enabled: open,
  });

  const groups: Group[] = data?.items ?? [];

  // Pre-select first group whenever the list arrives.
  useEffect(() => {
    if (open && !groupId && groups.length > 0) {
      setGroupId(groups[0].group_id);
    }
  }, [open, groupId, groups]);

  // Reset state on close.
  useEffect(() => {
    if (!open) {
      setError(null);
      setCaption("");
    }
  }, [open]);

  const selected = useMemo(
    () => groups.find((g) => g.group_id === groupId),
    [groups, groupId],
  );

  if (!open) return null;

  const handleShare = async () => {
    setError(null);
    if (!groupId) {
      setError("Pick a group to share to.");
      return;
    }
    setBusy(true);
    try {
      const post = await hubService.createHubPost(groupId, {
        source_artifact_type: source.artifact_type,
        source_id: source.source_id,
        caption: caption.trim() || undefined,
      });
      const slug = selected?.slug ?? groupId;
      onShared?.(post.post_id, slug);
      onClose();
      navigate(`/content-hub/${slug}`);
    } catch (err) {
      if (err instanceof AxiosError) {
        const detail = err.response?.data?.detail as
          | { code?: string; reason?: string }
          | undefined;
        switch (detail?.code) {
          case "ONBOARDING_REQUIRED":
          case "AGENT_REQUIRED":
            onClose();
            navigate(
              `/my-agent?return=${encodeURIComponent(window.location.pathname)}`,
            );
            return;
          case "NOT_A_MEMBER":
            setError("You'll need to join this group before posting.");
            break;
          case "UNSAFE_CAPTION":
            setError(
              detail.reason ??
                "That caption didn't pass our safety check — try a different one.",
            );
            break;
          case "SAFETY_UNAVAILABLE":
            setError("Our safety checker is taking a break. Try again in a minute.");
            break;
          default:
            setError(detail?.reason ?? "Couldn't share to Content Hub.");
        }
      } else {
        setError("Couldn't share to Content Hub. Try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="share-to-hub-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-8"
    >
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <header>
          <h2
            id="share-to-hub-title"
            className="text-xl font-semibold text-gray-900"
          >
            Share to Content Hub
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Your buddy will be the author — your real name and email never
            show up here.
          </p>
        </header>

        <div className="mt-4 flex flex-col gap-3">
          {isLoading ? (
            <p className="text-sm text-gray-500">Loading groups…</p>
          ) : groups.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-700">
              <p className="font-medium">No groups yet.</p>
              <p className="mt-1 text-xs text-gray-500">
                Create a group from Content Hub first, then come back to share.
              </p>
              <button
                type="button"
                className="mt-2 rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-white"
                onClick={() => {
                  onClose();
                  navigate("/content-hub");
                }}
              >
                Open Content Hub
              </button>
            </div>
          ) : (
            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
              Pick a group
              <select
                className="k12-input"
                value={groupId}
                onChange={(e) => setGroupId(e.target.value)}
                disabled={busy}
              >
                {groups.map((g) => (
                  <option key={g.group_id} value={g.group_id}>
                    {g.name} ({g.visibility})
                  </option>
                ))}
              </select>
            </label>
          )}

          {groups.length > 0 && (
            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
              Caption (optional)
              <textarea
                className="k12-input min-h-[64px]"
                value={caption}
                maxLength={MAX_CAPTION}
                onChange={(e) =>
                  setCaption(e.target.value.slice(0, MAX_CAPTION))
                }
                placeholder="Tell other kids what your story is about…"
                disabled={busy}
              />
              <span className="text-xs text-gray-500">
                {caption.length}/{MAX_CAPTION}
              </span>
            </label>
          )}

          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}
        </div>

        <footer className="mt-6 flex items-center justify-end gap-2">
          <button
            type="button"
            className="k12-button-secondary"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          {groups.length > 0 && (
            <button
              type="button"
              className="k12-button-primary"
              onClick={handleShare}
              disabled={busy || !groupId}
            >
              {busy ? "Sharing…" : "Share"}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
