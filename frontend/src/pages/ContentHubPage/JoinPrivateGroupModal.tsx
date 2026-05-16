import { useState } from "react";
import { createPortal } from "react-dom";

interface Props {
  open: boolean;
  onClose: () => void;
  onJoin: (inviteToken: string) => Promise<void>;
}

export default function JoinPrivateGroupModal({ open, onClose, onJoin }: Props) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  const handleClose = () => {
    setCode("");
    setError(null);
    setBusy(false);
    onClose();
  };

  const handleJoin = async () => {
    const inviteToken = code.trim();
    setError(null);
    if (!inviteToken) {
      setError("Type the group code your friend gave you.");
      return;
    }
    setBusy(true);
    try {
      await onJoin(inviteToken);
      handleClose();
    } catch {
      setError("That code didn't open a group. Check it and try again.");
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="join-private-group-title"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 px-4 py-8"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex flex-col gap-4">
          <div>
            <h2
              id="join-private-group-title"
              className="text-xl font-semibold text-gray-900"
            >
              Join a private group
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Ask your friend for the group code, then pop it in here.
            </p>
          </div>

          <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
            Group code
            <input
              className="k12-input"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void handleJoin();
                }
              }}
              placeholder="Paste the secret code"
              autoFocus
              disabled={busy}
            />
          </label>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              className="k12-button-secondary"
              onClick={handleClose}
              disabled={busy}
            >
              Cancel
            </button>
            <button
              type="button"
              className="k12-button-primary"
              onClick={() => void handleJoin()}
              disabled={busy || !code.trim()}
            >
              {busy ? "Joining..." : "Join group"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
