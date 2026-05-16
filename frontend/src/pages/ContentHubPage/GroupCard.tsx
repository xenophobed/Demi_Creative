/**
 * GroupCard — single group entry on the ContentHubPage directory.
 *
 * Issue: #451 | Parent epic: #437
 */

import { Lock, Users } from "lucide-react";
import type { Group } from "@/types/hub";

interface Props {
  group: Group;
  onOpen: () => void;
  onJoin?: () => void;
  joined: boolean;
}

export default function GroupCard({ group, onOpen, onJoin, joined }: Props) {
  const isPrivate = group.visibility === "private";
  return (
    <article className="k12-card group flex min-h-44 flex-col gap-3 p-5">
      <header className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-gray-900 line-clamp-1">
            {group.name}
          </h3>
          <p className="mt-1 flex items-center gap-1 text-xs font-medium text-gray-500">
            <Users size={13} />
            {group.member_count}{" "}
            {group.member_count === 1 ? "member" : "members"} ·{" "}
            {isPrivate ? "Private" : "Public"}
          </p>
        </div>
        <span
          className={[
            "k12-chip",
            isPrivate
              ? "bg-accent/45 text-yellow-800"
              : "bg-secondary/15 text-teal-700",
          ].join(" ")}
        >
          {isPrivate ? <Lock size={12} /> : null}
          {isPrivate ? "Private" : "Public"}
        </span>
      </header>

      {group.description && (
        <p className="text-sm text-gray-600 line-clamp-2">{group.description}</p>
      )}

      <footer className="mt-2 flex items-center gap-2">
        <button
          type="button"
          className="k12-button-primary px-3 py-1.5"
          onClick={onOpen}
        >
          Open
        </button>
        {onJoin && !joined && (
          <button
            type="button"
            className="k12-button-secondary px-3 py-1.5"
            onClick={onJoin}
          >
            {isPrivate ? "Join with invite" : "Join"}
          </button>
        )}
        {joined && (
          <span className="text-xs font-medium text-teal-700">
            ✓ Joined
          </span>
        )}
      </footer>
    </article>
  );
}
