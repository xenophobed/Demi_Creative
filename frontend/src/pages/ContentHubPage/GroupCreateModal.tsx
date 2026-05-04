/**
 * GroupCreateModal — create a new public or private group.
 *
 * On private create, the modal stays open after success to display
 * the invite_token (the backend exposes it ONCE in the create
 * response per the privacy posture from #448).
 *
 * Issue: #451 | Parent epic: #437
 */

import { useState } from "react";
import type { Group, GroupVisibility } from "@/types/hub";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreate: (payload: {
    name: string;
    visibility: GroupVisibility;
    description?: string;
    theme?: string;
  }) => Promise<Group>;
}

export default function GroupCreateModal({ open, onClose, onCreate }: Props) {
  const [name, setName] = useState("");
  const [visibility, setVisibility] = useState<GroupVisibility>("public");
  const [description, setDescription] = useState("");
  const [theme, setTheme] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<Group | null>(null);

  if (!open) return null;

  const handleCreate = async () => {
    setError(null);
    if (!name.trim()) {
      setError("Give your group a name.");
      return;
    }
    setBusy(true);
    try {
      const result = await onCreate({
        name: name.trim(),
        visibility,
        description: description.trim() || undefined,
        theme: theme.trim() || undefined,
      });
      setCreated(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We couldn't create the group. Try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleClose = () => {
    // Reset for the next open.
    setName("");
    setVisibility("public");
    setDescription("");
    setTheme("");
    setError(null);
    setCreated(null);
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-group-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-8"
    >
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        {created ? (
          <div className="flex flex-col gap-4">
            <h2
              id="create-group-title"
              className="text-xl font-semibold text-gray-900"
            >
              {created.visibility === "private"
                ? "Private group ready!"
                : "Public group ready!"}
            </h2>
            <p className="text-sm text-gray-600">
              <strong>{created.name}</strong> is live. Visit it any time from
              Content Hub.
            </p>
            {created.invite_token && (
              <div className="flex flex-col gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
                <p className="font-medium text-amber-900">
                  Share this invite link
                </p>
                <p className="text-xs text-amber-700">
                  We only show this once. Save it somewhere safe — the group
                  owner can copy it now and paste it to a friend.
                </p>
                <code className="block break-all rounded-md bg-white px-2 py-1.5 font-mono text-xs">
                  {created.invite_token}
                </code>
              </div>
            )}
            <button
              type="button"
              className="self-end rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700"
              onClick={handleClose}
            >
              Done
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <h2
              id="create-group-title"
              className="text-xl font-semibold text-gray-900"
            >
              Create a new group
            </h2>

            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
              Name
              <input
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                value={name}
                maxLength={80}
                onChange={(e) => setName(e.target.value.slice(0, 80))}
                placeholder="Dragons, Space Adventures…"
                disabled={busy}
              />
            </label>

            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
              Theme (optional)
              <input
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                value={theme}
                maxLength={50}
                onChange={(e) => setTheme(e.target.value.slice(0, 50))}
                placeholder="fantasy, science, nature…"
                disabled={busy}
              />
            </label>

            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
              Description (optional)
              <textarea
                className="min-h-[64px] rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                value={description}
                maxLength={500}
                onChange={(e) => setDescription(e.target.value.slice(0, 500))}
                disabled={busy}
              />
            </label>

            <fieldset className="flex flex-col gap-2 text-sm">
              <legend className="font-medium text-gray-700">Visibility</legend>
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  name="visibility"
                  value="public"
                  checked={visibility === "public"}
                  onChange={() => setVisibility("public")}
                  disabled={busy}
                />
                <span>
                  <strong>Public</strong> — anyone can browse and post.
                </span>
              </label>
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  name="visibility"
                  value="private"
                  checked={visibility === "private"}
                  onChange={() => setVisibility("private")}
                  disabled={busy}
                />
                <span>
                  <strong>Private</strong> — only people with the invite link
                  can join. We'll show the link once after you create it.
                </span>
              </label>
            </fieldset>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                onClick={handleClose}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:bg-gray-300"
                onClick={handleCreate}
                disabled={busy || !name.trim()}
              >
                {busy ? "Creating…" : "Create"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
